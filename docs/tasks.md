# Tasks — Plan de reestructuración (SDD)

> Desglose de tareas por fases (SDD · Fase 0). Estado: ☐ pendiente · ▶ en curso · ☑ hecho.
> Cada fase es mergeable de forma independiente y termina con su verificación.

## Fase 0 · Documentación SDD

- ☑ 0.1 Crear `docs/spec.md` (visión, objetivos, contrato, API genérica)
- ☑ 0.2 Crear `docs/design.md` (arquitectura, decisiones, flujos)
- ☑ 0.3 Crear `docs/tasks.md` (este documento)
- ☑ 0.4 Crear `docs/sims/inodes/spec.md` (fórmulas, rangos, API, criterios)
- ☑ 0.5 Crear `docs/sims/processes/spec.md` (máquina de estados, eventos)
- ☑ 0.6 Crear `docs/deploy.md` (pasos Render)

**Verificación**: revisión de coherencia entre spec/design/tasks.

## Fase 1 · Núcleo del marco en `core`

- ☑ 1.1 `core/exceptions.py` → `SimulationError`
- ☑ 1.2 `core/simulations.py` → `SimulationSpec`, `register`, `get`, `all_specs`
- ☑ 1.3 `core/views.py` → `make_index_view(slug)`, `make_action_view(slug)`
- ☑ 1.4 `core/templates/core/landing.html` → iterar `all_specs()` (sin cards hardcodeadas)
- ☑ 1.5 `core/urls.py` → landing
- ☑ 1.6 `core/tests.py` → registro, 404 slug inexistente, 400 JSON malformado, 405

**Verificación**: `manage.py check` + `manage.py test core`.

## Fase 2 · Migrar inodes a la nueva base

- ☑ 2.1 `inodes/services.py` → `inodes/simulation.py`: borrar código muerto
      (`resolve_position` líneas 254–559) y `_resolve_triple` duplicado (def. 562 y 725)
- ☑ 2.2 Eliminar el singleton `sim_instance`; constructor con `seed` determinista
- ☑ 2.3 Implementar `get_state()` + `dispatch(action, payload)` sobre el contrato
- ☑ 2.4 Registrar `SimulationSpec("inodes", …)` en `core`
- ☑ 2.5 `inodes/views.py` → fábricas de `core`; `urls.py` conserva `app_name`
- ☑ 2.6 Mover plantilla `templates/index.html` → `inodes/templates/inodes/index.html`
- ☑ 2.7 JS: adaptar `resolve` a `POST /api/action/` + semilla; randomize = nueva semilla
- ☑ 2.8 Tests: deterministas con `seed` fijo; cobertura de `get_state`/`dispatch`/errores

**Verificación**: `manage.py test inodes` + prueba manual (resolve, presets, randomize).

## Fase 3 · Arreglar processes y migrar a la nueva base

- ☑ 3.1 `processes/services.py` → `processes/simulation.py`: modelo **event-sourcing
      stateless** — constructor con `seed` + `events` (log), sin singleton;
      `get_state()` + `dispatch("apply", {"events": [...], "event": {...}})` con replay
      determinista y validación de precondiciones por transición
- ☑ 3.2 Registrar `SimulationSpec("processes", …)` en `core`
- ☑ 3.3 `processes/views.py` → fábricas de `core`; conservar `app_name`
- ☑ 3.4 UI/JS: control manual — **Añadir proceso**, selector de proceso, botones de
      transición (admit/dispatch/interrupt/io_wait/io_complete/exit), **Reiniciar**; el
      cliente mantiene el log de eventos y lo sincroniza desde `state.events`
- ☑ 3.5 Tests: crear, ciclo completo, interrupt, E/S, transición inválida, API, log
      corrupto

**Verificación**: `manage.py test processes` + prueba manual (crear, admitir,
despachar, interrumpir, E/S, salir).

## Fase 4 · Despliegue en Render

- ☑ 4.1 Dependencias: `gunicorn`, `whitenoise`
- ☑ 4.2 `config/settings.py` env-driven (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`) +
      `STATIC_ROOT` + whitenoise en `MIDDLEWARE` y `STORAGES`
- ☑ 4.3 `render.yaml` (BluePrint: build con `uv`, collectstatic, migrate, start gunicorn)
- ☑ 4.4 Completar `docs/deploy.md` con pasos exactos (repo → Render → env vars)
- ☑ 4.5 Verificar `manage.py check --deploy` y `collectstatic` en limpio

**Verificación**: `check --deploy` sin errores críticos + `collectstatic` OK.

## Fase 5 · Limpieza y pulido

- ☑ 5.1 Eliminar `año/` (residual `.ffshot`)
- ☑ 5.2 Actualizar `README.md` para apuntar a `docs/` y describir la nueva arquitectura
- ☑ 5.3 `ruff check .` limpio
- ☑ 5.4 Suite completa en verde: `manage.py test`
- ☑ 5.5 `git init` + `.gitignore` correcto (para subir a Render)

**Verificación**: `uv run ruff check .` + `manage.py test` + arranque manual.

## Criterios de aceptación globales

- A1 · La landing lista automáticamente inodes y processes desde el registro.
- A2 · No quedan singletons a nivel módulo en las apps de simulación.
- A3 · Ninguna vista contiene lógica de simulación.
- A4 · `manage.py test` en verde (core + inodes + processes).
- A5 · `ruff check .` sin errores.
- A6 · La app arranca con `DEBUG=False` y config por entorno (listo para Render).
