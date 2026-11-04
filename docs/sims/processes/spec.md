# Spec — Simulación del Ciclo de Vida de Procesos

> Spec de la simulación `processes` (SDD). Satisface el contrato de
> [spec.md §6](../spec.md).

## 1. Descripción

Anima la **máquina de estados de un proceso** (`NEW` ➜ `READY` ➜ `RUNNING` ➜ `WAITING` /
`TERMINATED`) integrando un **Bloque de Control de Proceso (PCB)** por proceso y un
**Planificador de Corto Plazo (Short-Term Scheduler)** con soporte para tres políticas:
- **FCFS (First-Come, First-Served)**: No preemptivo, cola FIFO estricta.
- **Round Robin (RR)**: Preemptivo por temporizador (`quantum` configurable).
- **Prioridades (`PRIORITY`)**: Cola `READY` ordenada por prioridad (`1` = máxima, `5` = mínima).

Ofrece dos modos de operación sobre la misma API stateless:
1. **Modo Demostración**: Guiones paso a paso específicos para cada algoritmo (`SCRIPT_FCFS`, `SCRIPT_RR`, `SCRIPT_PRIORITY`), con avance/retroceso manual (`Anterior` / `Paso a paso`) o reproducción automática con velocidad regulable.
2. **Modo Manual**: Laboratorio interactivo donde el usuario crea procesos, inspecciona y edita su PCB en una tarjeta flotante anclada al proceso, ejecuta ciclos de reloj (`tick`) y dispara transiciones de estado.

## 2. Estados y PCB

| Estado | Significado | Cola asociada |
|--------|-------------|---------------|
| `NEW` | Recién creado, aún no admitido | — |
| `READY` | En cola de listos en memoria principal | `ready_queue` |
| `RUNNING` | En ejecución dentro de la CPU (máx. 1 a la vez) | `running` |
| `WAITING` | Bloqueado esperando operación de E/S o evento | `waiting_queue` |
| `TERMINATED` | Ejecución completada | `terminated` |

Cada proceso posee un `ProcessControlBlock` (`pcbs[pid]`):
- `pid`: Identificador entero ≥ 1.
- `state`: Estado actual (`ProcessState`).
- `priority`: Entero de `1` (alta) a `5` (baja).
- `burst_time`: Ráfaga total estimada de CPU en ticks (`1..20`).
- `remaining_time`: Ticks de CPU restantes para completar la ejecución.
- `quantum_used`: Ticks consumidos en la ráfaga actual (solo se incrementa bajo `RR`).

## 3. Transiciones, eventos del planificador y precondiciones

Cada acción es un **evento** enviado a `dispatch("apply", ...)`. Si la precondición falla, el evento no se aplica y se devuelve `applied: false` con un `reason` didáctico que la UI presenta mediante un `<dialog>` nativo de alerta del SO.

| Evento | Transición / Efecto | Precondición |
|--------|---------------------|--------------|
| `create` | — ➜ `NEW` | `pid` entero ≥ 1 no existente; `priority` (1-5) y `burst_time` (1-20) opcionales |
| `admit` | `NEW` ➜ `READY` | El proceso está en `NEW` (se inserta en `ready_queue` según algoritmo) |
| `dispatch` | `READY` ➜ `RUNNING` | CPU libre (`running is None`) y proceso en `READY` (si se omite `pid`, despacha `next_scheduled`) |
| `interrupt` | `RUNNING` ➜ `READY` | El proceso es el que está en `RUNNING` |
| `io_wait` | `RUNNING` ➜ `WAITING` | El proceso es el que está en `RUNNING` |
| `io_complete` | `WAITING` ➜ `READY` | El proceso está en `WAITING` |
| `exit` | `RUNNING` ➜ `TERMINATED` | El proceso es el que está en `RUNNING` |
| `tick` | Avanza 1 ciclo de CPU | Hay un proceso en `RUNNING` (`running is not None`). Decrementa `remaining_time`; si llega a 0 transiciona a `TERMINATED`. En `RR`, incrementa `quantum_used` y si alcanza `quantum` dispara `interrupt`. |
| `set_algorithm` | Cambia política (`FCFS`, `RR`, `PRIORITY`) | Algoritmo válido; reordena `ready_queue` inmediatamente |
| `update_pcb` | Modifica `priority` o `burst_time` | Proceso existente y no `TERMINATED`; reordena `ready_queue` si cambia `priority` |

## 4. Modelo stateless (event-sourcing)

El estado es una función pura del **log de eventos**:

```
estado = replay(log de eventos)
```

- El cliente guarda localmente el log (`events`) y lo envía completo en cada petición.
- Para aplicar un evento nuevo, el cliente envía `{"events": [...log...], "event": {...}}`.
- Para retroceder un paso o reconstruir un punto anterior, el cliente envía `{"events": [...prefijo...]}`.
- **Reiniciar** = aplicar con `events: []` (estado vacío).

## 5. API

### Estado (`get_state()`)

```json
{
  "meta": { "slug": "processes", "seed": 1, "action_url": "/processes/api/action/" },
  "pids": [1, 2],
  "states": { "1": "READY", "2": "RUNNING" },
  "pcbs": {
    "1": { "pid": 1, "state": "READY", "priority": 2, "burst_time": 4, "remaining_time": 4, "quantum_used": 0 },
    "2": { "pid": 2, "state": "RUNNING", "priority": 1, "burst_time": 3, "remaining_time": 2, "quantum_used": 1 }
  },
  "ready_queue": [1],
  "waiting_queue": [],
  "running": 2,
  "terminated": [],
  "algorithm": "RR",
  "quantum": 2,
  "next_scheduled": 1,
  "current_time": 1,
  "events": [ ... ],
  "history": [ ... ]
}
```

### Acciones (`dispatch`)

| Acción | Payload | Resultado |
|--------|---------|-----------|
| `apply` | `{"events": [...], "event": {...} \| null}` | `{"applied": bool, "reason": str, "event": {...}}` |

## 6. Criterios de aceptación

- CA1 · Estado inicial (`events: []`): sin procesos, `running=None`, `algorithm="FCFS"`.
- CA2 · `create` añade un proceso en `NEW` con su PCB inicializado.
- CA3 · Secuencia `admit` ➜ `dispatch` ➜ `exit` deja el proceso en `TERMINATED`.
- CA4 · `interrupt` sobre el `RUNNING` lo devuelve a `READY` y libera la CPU.
- CA5 · Una transición inválida o `tick` con CPU inactiva responde `applied=false` con `reason` y no altera el log.
- CA6 · En `FCFS` o `PRIORITY`, `tick` no incrementa `quantum_used` ni desaloja por quantum; en `RR` desaloja al alcanzar `quantum`.
- CA7 · En `PRIORITY`, `ready_queue` y `next_scheduled` se ordenan por `priority` ascendente (1 antes que 3).
- CA8 · `update_pcb` permite ajustar `priority` y `burst_time` en modo manual y reordena `ready_queue`.
