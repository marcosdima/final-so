# Spec — Simulación del Ciclo de Vida de Procesos

> Spec de la simulación `processes` (SDD). Satisface el contrato de
> [spec.md §6](../spec.md).

## 1. Descripción

Anima la **máquina de estados de un proceso** (NEW ➜ READY ➜ RUNNING ➜ WAITING /
TERMINATED) con **control manual**: el usuario crea procesos a mano y dispara
transiciones (admitir, despachar, interrumpir, espera/fin de E/S, salir) sobre el
proceso que elija. La UI desplaza los tokens entre contenedores (animación FLIP).

## 2. Estados

| Estado | Significado | Cola asociada |
|--------|-------------|---------------|
| `NEW` | Recién creado, aún no admitido | — |
| `READY` | En cola de listos | `ready_queue` |
| `RUNNING` | En la CPU (máx. 1 a la vez) | `running` |
| `WAITING` | Esperando E/S | `waiting_queue` |
| `TERMINATED` | Finalizado | `terminated` |

## 3. Transiciones y precondiciones

Cada acción es un **evento** `{type, pid}`. Si la precondición falla, el evento no se
aplica y se devuelve `applied: false` con un `reason` (didáctico).

| Evento | Transición | Precondición |
|--------|------------|--------------|
| `create` | — ➜ NEW | PID entero ≥ 1 y aún no usado |
| `admit` | NEW ➜ READY | el proceso está en NEW |
| `dispatch` | READY ➜ RUNNING | CPU libre y proceso en READY |
| `interrupt` | RUNNING ➜ READY | el proceso es el que está RUNNING |
| `io_wait` | RUNNING ➜ WAITING | el proceso es el que está RUNNING |
| `io_complete` | WAITING ➜ READY | el proceso está en WAITING |
| `exit` | RUNNING ➜ TERMINATED | el proceso es el que está RUNNING |

## 4. Modelo stateless (event-sourcing)

El estado es una función pura del **log de eventos** (la secuencia de transiciones
aplicadas):

```
estado = replay(log de eventos)
```

- El cliente guarda localmente el log (`events`) y lo envía completo en cada petición.
- Para aplicar un evento nuevo, el cliente manda `{"events": [...log...], "event": {...}}`.
  El servidor replay el log, valida y aplica el evento nuevo, y devuelve el **log
  efectivo** (el cliente lo sincroniza desde `state.events`).
- Un evento inválido **no** se añade al log; el estado queda como estaba y se devuelve el
  motivo.
- **Reiniciar** = aplicar con `events: []` (estado vacío).

Esto permite control manual ilimitado sin memoria de servidor: dos visitantes en el mismo
log ven exactamente lo mismo (clave para Render).

## 5. API

### Estado (`get_state()`)

```json
{
  "meta": { "slug": "processes", "seed": 1 },
  "pids": [1, 2],
  "states": { "1": "READY", "2": "RUNNING" },
  "ready_queue": [1], "waiting_queue": [], "running": 2, "terminated": [],
  "events": [ { "type": "create", "pid": 1 }, … ],
  "history": [ { "event": {…}, "state": {…} }, … ]
}
```

### Acciones (`dispatch`)

| Acción | Payload | Resultado |
|--------|---------|-----------|
| `apply` | `{"events": [...], "event": {type, pid} \| null}` | `{"applied": bool, "reason": str, "event": {…}}` |

- `event: null` ⇒ sólo reconstruir el estado del log (sin aplicar nada).
- `events: []` + `event: null` ⇒ estado inicial (reinicio).

### Errores de dominio (`SimulationError` ⇒ 400)

- `events` no es una lista.
- Algún evento del log es inválido (log corrupto).

> Un evento nuevo inválido **no** es un 400: responde 200 con `applied: false` y `reason`.

## 6. Contrato de determinismo

Mismo log ⇒ mismo estado para cualquier cliente. La aleatoriedad (`seed`) no afecta al
guion (se conserva por uniformidad del contrato).

## 7. Criterios de aceptación

- CA1 · Estado inicial (`events: []`): sin procesos, `running=None`.
- CA2 · `create` añade un proceso en NEW; `pids` lo refleja.
- CA3 · Secuencia admit ➜ dispatch ➜ exit deja el proceso en TERMINATED.
- CA4 · `interrupt` sobre el RUNNING lo devuelve a READY y libera la CPU.
- CA5 · Una transición inválida responde `applied=false` con `reason` y no altera el log.
- CA6 · La página carga con 200 y el estado embebido es coherente.

## 8. UI asociada

- Plantilla: `processes/templates/processes/index.html` (extiende `base.html`).
- JS: `static/processes/js/main.js` (render FLIP + panel de estado + log en el cliente).
- Controles: **Añadir proceso**, **Reiniciar**, selector de proceso objetivo y botones de
  transición (Admitir, Despachar, Interrumpir, E/S espera, E/S fin, Salir). Clic en un
  token también lo selecciona.
