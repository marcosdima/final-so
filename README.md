# Simulador de Sistemas Operativos

Plataforma web didáctica en **Django** que aloja simulaciones interactivas de conceptos de
Sistemas Operativos. Actualmente incluye:

- **Inodos y disco**: traducción de posiciones lógicas de archivo a bloques físicos
  fragmentados (punteros directos e indirectos simple/doble/triple).
- **Ciclo de vida de procesos**: máquina de estados NEW / READY / RUNNING / WAITING /
  TERMINATED con eventos paso a paso.

Gestionado con **`uv`** e interfaz en **Dark Theme** con iconografía **Lucide**.

> La arquitectura, los requisitos y el contrato de simulaciones se documentan en
> [`docs/`](docs/). Para desplegar en Render, ver [`docs/deploy.md`](docs/deploy.md).

## Arquitectura (resumen)

Cada simulación es una **app Django autocontena** (`inodes/`, `processes/`) con su lógica
pura (`simulation.py`), plantilla, JS y tests. El marco compartido vive en **`core/`**:

- `core/spec.py` — contrato `Simulation` + `SimulationSpec`.
- `core/simulations.py` — catálogo/registro de simulaciones.
- `core/views.py` — vistas genéricas (`make_index_view` / `make_action_view`) parametrizadas
  por slug; la landing se genera automáticamente desde el registro.

Las simulaciones son **stateless y deterministas**: el estado se deriva de una `seed` (y, en
procesos, del número de paso), por lo que funcionan igual con múltiples workers (Render).

**API uniforme** por simulación:

- `GET /<slug>/` — página SSR con el estado inicial embebido.
- `POST /<slug>/api/action/` — `{"seed":42, "action":"resolve", "payload":{...}}` →
  `{"state":..., "result":...}`.

### Añadir una simulación nueva

1. Crear la app (`simulation.py` con `get_state`/`dispatch` + `SPEC`, plantilla, JS, tests).
2. Registrarla con una línea en `core/simulations.py`.

Aparecerá sola en la landing y dispondrá de la API genérica.

## Puesta en marcha

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Abre [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

### Tests

```bash
uv run python manage.py test
```

### Lint

```bash
uv run ruff check .
```

## Documentación

- [`docs/spec.md`](docs/spec.md) — requisitos y contrato de simulaciones.
- [`docs/design.md`](docs/design.md) — arquitectura y decisiones de diseño.
- [`docs/tasks.md`](docs/tasks.md) — plan de trabajo por fases.
- [`docs/deploy.md`](docs/deploy.md) — despliegue en Render.
- [`docs/sims/`](docs/sims/) — spec de cada simulación.
