# Spec — Simulación del Ciclo de Vida de Procesos

> Spec de la simulación `processes` (SDD · Fase 0). Satisface el contrato de
> [spec.md §6](../spec.md).

## 1. Descripción

Anima la **máquina de estados de un proceso** (NEW ➜ READY ➜ RUNNING ➜ WAITING /
TERMINATED) aplicando una secuencia fija de eventos. Cada evento muta los estados, la cola
de listos, la cola de espera y la CPU; la UI desplaza visualmente los tokens entre
contenedores (animación FLIP).

## 2. Estados

| Estado | Significado | Representación UI |
|--------|-------------|-------------------|
| `NEW` | Recién creado, aún no admitido | Contenedor "New" |
| `READY` | En cola de listos (`ready_queue`) | Contenedor "Ready" |
| `RUNNING` | En la CPU (`running`) | Contenedor "Running" (resaltado) |
| `WAITING` | Esperando E/S (`waiting_queue`) | Contenedor "Waiting" |
| `TERMINATED` | Finalizado (`terminated`) | Contenedor "Terminated" |

## 3. Procesos y eventos

- PIDs por defecto: `[1, 2, 3]`.
- Guion de eventos por defecto (`DEFAULT_PROCESS_EVENTS`): **14 eventos** que recorren
  admit/dispatch/io_wait/io_complete/interrupt/exit. El guion es parte del estado.

### Transiciones y precondiciones

| Evento | Desde ➜ Hasta | Precondición (si falla ⇒ `applied: false` + `reason`) |
|--------|---------------|-------------------------------------------------------|
| `admit` | NEW ➜ READY | el proceso está en NEW |
| `dispatch` | READY ➜ RUNNING | CPU libre y proceso en READY |
| `interrupt` | RUNNING ➜ READY | el proceso es el que está RUNNING |
| `io_wait` | RUNNING ➜ WAITING | el proceso es el que está RUNNING |
| `io_complete` | WAITING ➜ READY | el proceso está en WAITING |
| `exit` | RUNNING ➜ TERMINATED | el proceso es el que está RUNNING |

## 4. Modelo stateless

El estado es una función pura de `(seed, step)`:

```
estado(step) = replay de los primeros `step` eventos sobre el guion
```

- El cliente guarda localmente el índice de paso (`step`), inicialmente `0`.
- **Siguiente paso** ⇒ `POST {"action":"step","payload":{"step": n+1}}`; el servidor
  recrea la máquina y replay `n+1` eventos, devolviendo el estado resultante y el detalle
  del evento aplicado en la posición `n`.
- **Reiniciar** ⇒ `step = 0` (sin llamada a red, o con `step=0` explícito).
- **Auto** ⇒ el cliente repite "siguiente paso" en intervalo.

`seed` no afecta al guion (es fijo) pero se mantiene en el contrato por uniformidad y
para futuros guioneos aleatorios.

## 5. API

### Estado (`get_state()`)

```json
{
  "meta": { "slug": "processes", "seed": 1 },
  "pids": [1, 2, 3],
  "states": { "1": "READY", "2": "NEW", "3": "NEW" },
  "ready_queue": [1], "waiting_queue": [], "running": null, "terminated": [],
  "events": [ … ], "event_index": 2, "total_events": 14,
  "history": [ { "event": {…}, "state": {…} }, … ]
}
```

### Acciones (`dispatch`)

| Acción | Payload | Resultado |
|--------|---------|-----------|
| `step` | `{"step": n}` (n = índice destino, 0 ≤ n ≤ total) | `{"applied": bool, "reason": str, "event": {…}, "event_index": n}` |

- `step: 0` ⇒ estado inicial, sin eventos aplicados (`result.event = null`).
- `step > total_events` ⇒ `SimulationError` (400).
- Nota: `history` se reconstruye como el replay de los `n` eventos aplicados.

### Errores de dominio (`SimulationError` ⇒ 400)

- `step` no entero o fuera de `[0, total_events]`.
- Evento cuya precondición no se cumple durante el replay (no debería ocurrir con el
  guion por defecto; protegido).

## 6. Contrato de determinismo

`(seed=k, step=n)` ⇒ mismo estado para cualquier cliente. Dos visitantes en el mismo paso
ven exactamente lo mismo (condición clave para Render).

## 7. Criterios de aceptación

- CA1 · Estado inicial (`step=0`): `running=None`, `event_index=0`, todos en NEW.
- CA2 · Replay completo (`step=14`): los 3 procesos terminan; `applied=true` en todos.
- CA3 · `step=15` ⇒ `SimulationError`.
- CA4 · `step=n` responde lo mismo en dos peticiones distintas (stateless).
- CA5 · La página carga con 200 y el estado embebido es coherente.

## 8. UI asociada

- Plantilla: `processes/templates/processes/index.html` (extiende `base.html`).
- JS: `static/processes/js/main.js` (render con animación FLIP + panel de estado).
- Controles: `Siguiente paso`, `Auto/Pausa`, `Reiniciar`; panel de texto de estado.
