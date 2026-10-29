# Design — Arquitectura del marco de simulaciones

> Documento de diseño (SDD · Fase 0). Complementa a [spec.md](spec.md) respondiendo al
> **cómo** técnico. Si el spec cambia, este documento se actualiza en la misma PR.

## 1. Decisiones de arquitectura

### D1 · Una app Django por simulación + un núcleo compartido en `core`

Se mantiene el patrón de *apps por característica* que Django promueve y que se espera
ver en un examen:

```
inodes/    → lógica + plantilla + JS + tests de la simulación de inodos
processes/ → lógica + plantilla + JS + tests del ciclo de vida de procesos
core/      → el "marco": registro, vistas genéricas, excepciones, landing
config/    → settings/urls/wsgi del proyecto
```

Cada app de simulación es **autocontenida** (C3): su lógica, sus templates, su JS y sus
tests. Añadir una simulación = añadir un paquete de este estilo + registrar su spec.

**Alternativa descartada**: una única app `simulations` con todas las lógicas juntas.
Facilita copiar código, pero rompe la separación por feature y se ve peor en el examen.

### D2 · Registro central (`core/simulations.py`) con specs explícitas

Las specs se importan y registran explícitamente en `core/simulations.py`:

```python
SIMULATIONS: dict[str, SimulationSpec] = {}

def register(spec: SimulationSpec) -> None: ...
def get(slug: str) -> SimulationSpec | None: ...
def all_specs() -> list[SimulationSpec]: ...
```

**Alternativa descartada**: auto-descubrimiento mediante `AppConfig.ready()` + introspección.
Es "mágico": dificulta seguir el código en el examen y hace frágil el orden de importación.
La lista explícita es trivial de leer y de depurar.

### D3 · API stateless con semilla (clave para Render)

El estado **no vive en el servidor**. Cada petición lleva lo necesario para reconstruirlo:

- **Inodos**: la disposición de bloques se deriva de `seed`. "Otro disco" = nueva semilla
  (el cliente la cambia y recarga). Resolver una posición es una función pura
  `resolve_position(pos)`.
- **Procesos**: el estado es una función pura de `(seed, n_pasos)`. "Siguiente paso" envía
  `payload.step = n+1`; el servidor recrea la máquina y replay determinista de `n+1` eventos
  (14 eventos ⇒ coste nulo). "Reiniciar" = `step = 0`.

Ventajas: sin condiciones de carrera, sin estado compartido entre visitantes, sin pérdida
de estado al reiniciar el dyno, y respuestas idempotentes fáciles de testear.

**Alternativa descartada**: singleton global mutable (`sim_instance`) — el estado se
comparte entre usuarios y muere con el proceso. Y sesión de Django — requiere backend
persistente en Render y complica el estadoless.

### D4 · Vistas genéricas parametrizadas por slug (fábricas en `core`)

`core/views.py` expone fábricas de vistas. Cada app delega en ellas en su `views.py`:

```python
# inodes/views.py
index = make_index_view("inodes")
action_api = make_action_view("inodes")
```

Así se eliminan vistas/JSON-repetidos pero se conservan `app_name` + `urlpatterns` por app
(idiomatismos Django visibles en el examen: `reverse("inodes:index")`, `include`).

La vista genérica hace exactamente:

1. Busca la spec por `slug` (⇒ 404 si no existe).
2. `index`: `factory(seed=request.GET seed)` → `get_state()` → render SSR + `json_script`.
3. `action_api`: parsea JSON (⇒ 400 si malformed) → construye la simulación →
   `dispatch(action, payload)` → `{"state": ..., "result": ...}`.
4. `SimulationError` ⇒ 400 con `{"error": str(exc)}`.

### D5 · Semilla llega por querystring y por el estado embebido

- `GET /<slug>/?seed=42` fija la semilla de la página renderizada.
- La semilla activa se incluye dentro del `json_script` (campo `meta.seed`) para que el JS
  la reenvíe en cada `POST` sin estado de sesión.

### D6 · `services.py` → `simulation.py`

Se renombra el módulo de lógica para reflejar su rol dentro del nuevo contrato
(`InodeSimulation`, `ProcessLifecycleSimulation`). Se elimina el singleton a nivel módulo
y todo código muerto heredado.

## 2. Estructura de directorios objetivo

```
FINAL/
├── config/                    # settings (env-driven), urls, wsgi, asgi
├── core/
│   ├── simulations.py         # SimulationSpec + registro
│   ├── exceptions.py          # SimulationError
│   ├── views.py               # make_index_view / make_action_view
│   ├── urls.py                # landing
│   ├── tests.py               # registro + API genérica
│   └── templates/core/landing.html
├── inodes/
│   ├── simulation.py          # InodeSimulation (lógica pura, seed)
│   ├── views.py               # delega en core
│   ├── urls.py                # app_name="inodes"
│   ├── templates/inodes/index.html
│   ├── static/inodes/js/…
│   └── tests.py
├── processes/                 # mismo esquema
├── templates/                 # base.html + cotton
├── static/css/…
├── docs/                      # SDD
├── render.yaml
└── manage.py / pyproject.toml / uv.lock
```

## 3. Flujo de una petición

```
GET /inodes/?seed=42
  └─ config.urls → include("inodes.urls") → inodes.views.index (= make_index_view("inodes"))
       └─ core.get("inodes") → spec
            └─ spec.factory(seed=42) → InodeSimulation
                 └─ sim.get_state() → contexto → render SSR + json_script

POST /inodes/api/action/  {"seed":42,"action":"resolve","payload":{"pos":18}}
  └─ … → core.views.action_api
       └─ parsea JSON → spec.factory(seed=42) → sim.dispatch("resolve", {"pos":18})
            └─ {"state": {…}, "result": {…}}   (SimulationError ⇒ 400)
```

## 4. Mapa de responsabilidades

| Módulo | Responsabilidad | NO debe hacer |
|--------|-----------------|---------------|
| `core/simulations.py` | Catálogo de specs | Contener lógica de simulación |
| `core/views.py` | HTTP genérico (parseo, render, errores) | Conocer detalles de una sim concreta |
| `<app>/simulation.py` | Lógica pura determinista | Importar de Django ni de otras sims |
| `<app>/views.py` | Delegar en `core` | Repetir lógica |
| `<app>/static/.../js` | Consumir la API y pintar | Recalcular lógica de negocio (salvo fallback UI) |

## 5. Despliegue (resumen; detalle en deploy.md)

- **Runtime**: gunicorn (WSGI) + whitenoise (static sin CDN).
- **Config por variables de entorno**: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`.
- **Static**: `collectstatic` en build; `STATIC_ROOT` servido por whitenoise.
- **DB**: SQLite por defecto (suficiente: sin modelos de negocio; el disco de Render es
  efímero y el estado es stateless). `migrate` corre en el build para admin/auth.
- **Orquestación**: `render.yaml` (BluePrint) para reproducir el servicio.

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Replay de eventos caro si creciera el guion | Hoy: 14 eventos. Si creciera, cachear por `(seed, n)` en memoria con TTL |
| JS dependiente de IDs/DOM concretos | Se toca sólo la capa de fetch/estado; el render se conserva |
| Semilla ausente ⇒ estado no reproducible | Semilla por defecto determinista en `factory` |
| Dependencias de red (Google Fonts, Lucide CDN) | Se aceptan (didáctico); no bloquean el despliegue |

## 7. Convenciones de código

- Type hints en la lógica de simulación; docstrings breves en español.
- Nombres de acciones en inglés (`resolve`, `step`, `randomize`); textos didácticos en
  español (son contenido del examen).
- `ruff` como linter/formateador (config en `pyproject.toml`).
