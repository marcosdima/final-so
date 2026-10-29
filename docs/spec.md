# Spec — Marco de Simuladores de Sistemas Operativos

> Documento maestro de requisitos (SDD · Fase 0). Define **qué** es el producto y el
> **contrato** que toda simulación debe cumplir. El *cómo* vive en [design.md](design.md).

## 1. Visión

Plataforma web didáctica (Django) que aloja **simulaciones interactivas** de conceptos de
Sistemas Operativos. Cada simulación traduce un concepto (inodos, ciclo de vida de procesos,
…) a una interfaz visual con explicación paso a paso.

El objetivo de esta reestructuración es doble:

1. **Facilidad de desarrollo**: añadir una simulación nueva debe ser barato y repetible.
2. **Corrección estructural Django**: mostrar en el examen una arquitectura idiomática
   (apps, `urls` namespaced, `reverse`, separación vista/lógica), sin sobre-ingeniería.

## 2. Objetivos

| # | Objetivo | Criterio de verificación |
|---|----------|--------------------------|
| O1 | Añadir una simulación sin tocar vistas/URLs genéricas | Nueva sim = 1 módulo de lógica + plantilla + JS + tests |
| O2 | API JSON uniforme para todas las simulaciones | Todas las interacciones vía `POST /<slug>/api/action/` |
| O3 | Estado determinista y reproducible | Misma semilla + mismas acciones ⇒ mismo estado (tests estables) |
| O4 | Funcionar en un entorno con múlticos workers (Render) | Cero estado compartido en memoria entre peticiones |
| O5 | Landing y navegación auto-generadas | Añadir la spec ⇒ aparece la card sin tocar la plantilla |
| O6 | Despliegue público reproducible en Render | `render.yaml` + `docs/deploy.md` reproducibles |

## 3. No objetivos (explícitamente fuera de alcance)

- Seguridad de producción (autenticación, rate-limiting, hardening). Es un artefacto
  didáctico para un examen; el admin queda protegido por login por defecto.
- Persistencia de datos de usuario. No hay modelos de negocio ni base de datos con datos.
- Múltiples simulaciones más allá de **inodes** y **processes** en esta iteración. La base
  debe *admitirlas*, pero no se implementan nuevas.

## 4. Actores y uso

- **Estudiante (usuario final)**: entra en la landing, elige una simulación, interactúa
  con la UI (inputs, chips, paso a paso). No se registra ni guarda estado.
- **Autor/desarrollador**: añade simulaciones cumpliendo el contrato de la §6.

## 5. Requisitos funcionales

- **RF1 · Landing de simulaciones**: página de inicio que lista dinámicamente todas las
  simulaciones registradas (título, descripción, icono, enlace).
- **RF2 · Página de simulación**: cada simulación renderiza su vista inicial completa
  server-side (SSR) y la hidrata con datos embebidos (`json_script`).
- **RF3 · API de acciones**: endpoint JSON único y uniforme por simulación para ejecutar
  acciones sobre el estado.
- **RF4 · Aleatorización reproducible**: las simulaciones aleatorias (inodos) reciben una
  semilla; "otro disco" equivale a cambiar de semilla.
- **RF5 · Errores coherentes**: entradas inválidas (posición fuera de rango, JSON
  malformado, acción desconocida, slug inexistente) devuelven 4xx con mensaje claro, nunca
  500.

## 6. Contrato de simulación

Toda simulación es una clase Python con este contrato mínimo:

```python
class Simulation:
    def get_state(self) -> dict:
        """Estado completo y serializable para render inicial y json_script."""

    def dispatch(self, action: str, payload: dict) -> dict:
        """Aplica una acción (accionable) y devuelve el nuevo estado + resultado."""
```

Y se publica mediante una `SimulationSpec` registrada en `core`:

```python
SimulationSpec(
    slug="inodes",                 # identificador URL y de registro
    title="Inodos y disco",        # título para landing/navegación
    description="...",             # descripción corta
    icon="hard-drive",             # icono Lucide
    factory=InodeSimulation,       # callable(seed=..., **params) -> Simulation
)
```

### Reglas del contrato

- **C1 — Determinismo**: `factory(seed=k)` + mismas acciones ⇒ mismas respuestas. Sin
  estado global mutado fuera de la instancia.
- **C2 — Pureza de la vista**: la vista no contiene lógica de simulación; sólo construye
  la spec, llama a `get_state`/`dispatch` y serializa.
- **C3 — Autocontención**: la lógica vive en `simulations.py` de su app; no importa de
  otras apps de simulaciones.
- **C4 — Errores de dominio**: el fallo de validación se expone lanzando
  `core.exceptions.SimulationError` (la capa HTTP lo traduce a 400).

## 7. Requisitos no funcionales

- **RNF1 · Rendimiento**: una acción resuelve en tiempo despreciable (< 50 ms); se permite
  recalcular el estado desde cero (es barato) en lugar de mantenerlo en servidor.
- **RNF2 · Simplicidad**: preferir convención sobre configuración; sin dependencias nuevas
  salvo las necesarias para desplegar.
- **RNF3 · Consistencia visual**: todas las páginas extienden `templates/base.html`
  (dark theme, Lucide, Fira Code/Inter).
- **RNF4 · Testeabilidad**: toda simulación se puede instanciar y probar aislada del HTTP.

## 8. API genérica (contrato HTTP)

Todas las simulaciones exponen, con `app_name` propio:

| Método | Ruta | Nombre | Descripción |
|--------|------|--------|-------------|
| GET | `/<slug>/` | `<slug>:index` | Página SSR + estado inicial embebido |
| POST | `/<slug>/api/action/` | `<slug>:action_api` | Ejecuta una acción (ver esquema) |

### Esquema de la petición (POST JSON)

```json
{
  "seed": 1234,
  "action": "resolve",
  "payload": { "pos": 10 }
}
```

- `seed` (entero, opcional): semilla para simulaciones aleatorias. Si se omite, se usa una
  por defecto (determinista) para que la página sea reproducible.
- `action` (string, obligatorio): nombre de la acción entendida por la simulación.
- `payload` (objeto, opcional): parámetros específicos de la acción.

### Esquema de la respuesta (200)

```json
{
  "state": { ... },
  "result": { ... }
}
```

- `state`: salida de `get_state()` tras aplicar la acción (hidrata la UI completa).
- `result`: detalle específico de la acción (p. ej. la resolución de un paso).

### Errores

| Código | Causa |
|--------|-------|
| 400 | JSON malformado, `action` ausente/desconocida, payload inválido (`SimulationError`) |
| 404 | `slug` no registrado |
| 405 | Método distinto de GET (index) / POST (action) |

## 9. Glossario

- **Posición lógica (base 1)**: índice de bloque del archivo tal como lo ve el usuario.
- **Bloque lógico N**: `N = posición - 1` (base 0), el que usan las fórmulas de inodos.
- **Semilla (seed)**: entero que determina por completo la disposición aleatoria simulada.
- **Spec / registro**: entrada del catálogo `core.simulations.SIMULATIONS`.

## 10. Referencias

- Diseño: [design.md](design.md)
- Tareas: [tasks.md](tasks.md)
- Despliegue: [deploy.md](deploy.md)
- Specs por simulación: [sims/inodes/spec.md](sims/inodes/spec.md),
  [sims/processes/spec.md](sims/processes/spec.md)
