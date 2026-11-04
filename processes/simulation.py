"""
Lógica de la simulación del ciclo de vida de procesos.

Módulo **puro** (sin Django). Implementa el contrato `Simulation` del marco
(`get_state` + `dispatch`) con un modelo **stateless de event-sourcing**:

- El cliente mantiene el **log de eventos** (la secuencia de transiciones aplicadas).
- El servidor es el único dueño de la máquina de estados: recibe el log completo,
  lo replay determinista y aplica encima el evento nuevo, validando sus precondiciones.

Incluye la representación formal de un Bloque de Control de Proceso (**PCB**) y
políticas de planificación del **Planificador de Corto Plazo** (Short-Term Scheduler)
como FCFS, Round Robin (con quantum) y Prioridades.

Ver `docs/sims/processes/spec.md` para la máquina de estados y las acciones.
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.exceptions import SimulationError
from core.spec import SimulationSpec


class ProcessState(str, Enum):
    NEW = "NEW"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    TERMINATED = "TERMINATED"


class SchedulingAlgorithm(str, Enum):
    FCFS = "FCFS"
    ROUND_ROBIN = "RR"
    PRIORITY = "PRIORITY"


# Transiciones válidas (para documentación/UI).
TRANSITIONS = {
    "create": "— ➜ NEW",
    "admit": "NEW ➜ READY",
    "dispatch": "READY ➜ RUNNING",
    "interrupt": "RUNNING ➜ READY",
    "io_wait": "RUNNING ➜ WAITING",
    "io_complete": "WAITING ➜ READY",
    "exit": "RUNNING ➜ TERMINATED",
}


@dataclass
class ProcessControlBlock:
    """Bloque de Control de Proceso (PCB).

    Contiene los atributos esenciales que el Sistema Operativo rastrea
    para cada proceso en memoria o ejecución.
    """

    pid: int
    state: ProcessState = ProcessState.NEW
    priority: int = 1  # 1 (más alta) a 5 (más baja)
    burst_time: int = 4  # Estimación de ráfaga de CPU en unidades de tiempo
    remaining_time: int = 4  # Tiempo restante de CPU para terminar
    quantum_used: int = 0  # Quantum consumido en la ráfaga actual (para Round Robin)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "state": self.state.value,
            "priority": self.priority,
            "burst_time": self.burst_time,
            "remaining_time": self.remaining_time,
            "quantum_used": self.quantum_used,
        }


@dataclass
class ProcessLifecycleSimulation:
    """Máquina de estados de procesos y planificador de CPU."""

    seed: int | None = None
    # Log de eventos aplicados (lo aporta el cliente; el servidor lo replay).
    events: list[dict[str, Any]] = field(default_factory=list)
    algorithm: SchedulingAlgorithm = SchedulingAlgorithm.FCFS
    quantum: int = 2

    def __post_init__(self) -> None:
        if self.seed is None:
            self.seed = random.randrange(2**31)
        self._handlers = {
            "create": self._handle_create,
            "admit": self._handle_admit,
            "dispatch": self._handle_dispatch,
            "interrupt": self._handle_interrupt,
            "io_wait": self._handle_io_wait,
            "io_complete": self._handle_io_complete,
            "exit": self._handle_exit,
            "tick": self._handle_tick,
            "set_algorithm": self._handle_set_algorithm,
        }
        self._rebuild(list(self.events))

    # ------------------------------------------------------------------
    # Reconstrucción (replay) del estado a partir del log
    # ------------------------------------------------------------------
    def _reset_state(self) -> None:
        self.pcbs: dict[int, ProcessControlBlock] = {}
        self.ready_queue: list[int] = []
        self.waiting_queue: list[int] = []
        self.running: int | None = None
        self.terminated: list[int] = []
        self.applied_events: list[dict[str, Any]] = []
        self.history: list[dict[str, Any]] = []
        self.current_time: int = 0
        self.algorithm = SchedulingAlgorithm.FCFS
        self.quantum = 2

    def _rebuild(self, events: list[dict[str, Any]]) -> None:
        """Reproduce el log desde cero. Cualquier evento inválido ⇒ SimulationError."""
        self._reset_state()
        for event in events:
            applied, reason = self._apply(event)
            if not applied:
                raise SimulationError(
                    f"Evento inválido en el historial ({reason})."
                )
            self.applied_events.append(event)
            self.history.append({"event": event, "state": self.get_state_snapshot()})

    # ------------------------------------------------------------------
    # Planificador de corto plazo (Scheduler)
    # ------------------------------------------------------------------
    def _sort_ready_queue(self) -> None:
        """Ordena la cola de listos según el algoritmo activo."""
        if self.algorithm == SchedulingAlgorithm.PRIORITY:
            # Menor número = mayor prioridad
            self.ready_queue.sort(key=lambda pid: self.pcbs[pid].priority)
        # FCFS y RR conservan el orden FIFO natural de inserción

    def _enqueue_ready(self, pid: int) -> None:
        if pid not in self.ready_queue:
            self.ready_queue.append(pid)
        self._sort_ready_queue()

    def get_next_scheduled_pid(self) -> int | None:
        """Devuelve el PID del próximo proceso a despachar según la política actual."""
        if not self.ready_queue:
            return None
        return self.ready_queue[0]

    # ------------------------------------------------------------------
    # Transiciones (la máquina de estados y acciones)
    # ------------------------------------------------------------------
    def _handle_set_algorithm(self, event_data: Any) -> tuple[bool, str]:
        algo_name = event_data.get("algorithm") if isinstance(event_data, dict) else event_data
        quantum = event_data.get("quantum", 2) if isinstance(event_data, dict) else 2
        try:
            self.algorithm = SchedulingAlgorithm(algo_name)
        except ValueError:
            return False, f"Algoritmo desconocido: '{algo_name}'."
        if isinstance(quantum, int) and quantum >= 1:
            self.quantum = quantum
        self._sort_ready_queue()
        return True, ""

    def _handle_create(self, event_data: Any) -> tuple[bool, str]:
        # event_data puede ser simplemente el PID o un dict con atributos de PCB
        if isinstance(event_data, dict):
            pid = event_data.get("pid")
            priority = event_data.get("priority", 1)
            burst = event_data.get("burst_time", 4)
        else:
            pid = event_data
            priority = 1
            burst = 4

        if isinstance(pid, bool) or not isinstance(pid, int) or pid < 1:
            return False, "PID inválido."
        if pid in self.pcbs:
            return False, f"P{pid} ya existe."

        pcb = ProcessControlBlock(
            pid=pid,
            state=ProcessState.NEW,
            priority=priority,
            burst_time=burst,
            remaining_time=burst,
        )
        self.pcbs[pid] = pcb
        return True, ""

    def _handle_admit(self, pid: Any) -> tuple[bool, str]:
        pcb = self.pcbs.get(pid)
        if not pcb or pcb.state != ProcessState.NEW:
            return False, f"P{pid} no está en NEW."
        pcb.state = ProcessState.READY
        self._enqueue_ready(pid)
        return True, ""

    def _handle_dispatch(self, pid: Any = None) -> tuple[bool, str]:
        if self.running is not None:
            return False, f"CPU ocupada por P{self.running}."

        # Si no se pasa PID, el scheduler elige al primero de la cola
        if pid is None or pid == 0:
            if not self.ready_queue:
                return False, "No hay procesos en la cola de listos (READY)."
            pid = self.ready_queue[0]

        pcb = self.pcbs.get(pid)
        if not pcb or pcb.state != ProcessState.READY:
            return False, f"P{pid} no está en READY."
        if pid not in self.ready_queue:
            return False, f"P{pid} no está en la cola de listos."

        self.ready_queue.remove(pid)
        self.running = pid
        pcb.state = ProcessState.RUNNING
        pcb.quantum_used = 0
        return True, ""

    def _handle_interrupt(self, pid: Any) -> tuple[bool, str]:
        if self.running != pid:
            return False, f"P{pid} no está en RUNNING."
        pcb = self.pcbs[pid]
        self.running = None
        pcb.state = ProcessState.READY
        pcb.quantum_used = 0
        self._enqueue_ready(pid)
        return True, ""

    def _handle_io_wait(self, pid: Any) -> tuple[bool, str]:
        if self.running != pid:
            return False, f"P{pid} no está en RUNNING."
        pcb = self.pcbs[pid]
        self.running = None
        pcb.state = ProcessState.WAITING
        pcb.quantum_used = 0
        if pid not in self.waiting_queue:
            self.waiting_queue.append(pid)
        return True, ""

    def _handle_io_complete(self, pid: Any) -> tuple[bool, str]:
        pcb = self.pcbs.get(pid)
        if not pcb or pid not in self.waiting_queue:
            return False, f"P{pid} no está en WAITING."
        self.waiting_queue.remove(pid)
        pcb.state = ProcessState.READY
        self._enqueue_ready(pid)
        return True, ""

    def _handle_exit(self, pid: Any) -> tuple[bool, str]:
        if self.running != pid:
            return False, f"P{pid} no está en RUNNING."
        pcb = self.pcbs[pid]
        self.running = None
        pcb.state = ProcessState.TERMINATED
        pcb.remaining_time = 0
        if pid not in self.terminated:
            self.terminated.append(pid)
        return True, ""

    def _handle_tick(self, _: Any = None) -> tuple[bool, str]:
        """Avanza una unidad de tiempo en la CPU (tick de reloj).

        Solo se aplica si hay un proceso en ejecución (RUNNING).
        - Decrementa remaining_time.
        - Si está bajo Round Robin, aumenta quantum_used.
        - Si finaliza (remaining_time <= 0), pasa a TERMINATED.
        - Si está en Round Robin y agotó el quantum, se interrumpe y vuelve a READY.
        """
        if self.running is None:
            return False, "La CPU está inactiva (IDLE): no hay ningún proceso en ejecución para consumir ciclos."

        self.current_time += 1
        pcb = self.pcbs[self.running]
        pcb.remaining_time = max(0, pcb.remaining_time - 1)

        # Quantum solo aplica en Round Robin
        if self.algorithm == SchedulingAlgorithm.ROUND_ROBIN:
            pcb.quantum_used += 1

        if pcb.remaining_time == 0:
            return self._handle_exit(pcb.pid)

        if self.algorithm == SchedulingAlgorithm.ROUND_ROBIN and pcb.quantum_used >= self.quantum:
            return self._handle_interrupt(pcb.pid)

        return True, ""

        return True, ""

    def _apply(self, event: dict[str, Any]) -> tuple[bool, str]:
        if not isinstance(event, dict):
            return False, "Evento inválido."
        ev_type = event.get("type")
        handler = self._handlers.get(ev_type)
        if handler is None:
            return False, f"Evento desconocido: '{ev_type}'."

        if ev_type in ("tick",):
            return handler(None)
        if ev_type in ("set_algorithm",):
            return handler(event.get("payload") or event)
        if ev_type == "create" and ("priority" in event or "burst_time" in event):
            return handler(event)

        return handler(event.get("pid"))

    # ------------------------------------------------------------------
    # Contrato Simulation: estado y acciones
    # ------------------------------------------------------------------
    def get_state_snapshot(self) -> dict[str, Any]:
        return {
            "states": {str(pid): pcb.state.value for pid, pcb in self.pcbs.items()},
            "pcbs": {str(pid): pcb.to_dict() for pid, pcb in self.pcbs.items()},
            "ready_queue": list(self.ready_queue),
            "waiting_queue": list(self.waiting_queue),
            "running": self.running,
            "terminated": list(self.terminated),
            "algorithm": self.algorithm.value,
            "quantum": self.quantum,
            "next_scheduled": self.get_next_scheduled_pid(),
            "current_time": self.current_time,
        }

    def get_state(self) -> dict[str, Any]:
        return {
            "meta": {"slug": "processes", "seed": self.seed},
            "pids": list(self.pcbs.keys()),
            **self.get_state_snapshot(),
            "events": list(self.applied_events),
            "history": self.history,
        }

    def dispatch(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta una acción. Ver `docs/sims/processes/spec.md` §5.

        - ``apply``: replay de ``payload.events`` (log completo) y, opcionalmente,
          aplicación de ``payload.event`` (evento nuevo) sobre ese estado.
        """
        if action == "apply":
            events = payload.get("events", [])
            if not isinstance(events, list):
                raise SimulationError("'events' debe ser una lista de eventos.")
            self._rebuild(events)

            new_event = payload.get("event")
            if new_event is None:
                # Sólo reconstrucción (sin evento nuevo).
                return {"applied": True, "reason": "", "event": None}

            applied, reason = self._apply(new_event)
            if applied:
                self.applied_events.append(new_event)
                self.history.append(
                    {"event": new_event, "state": self.get_state_snapshot()}
                )
            return {"applied": applied, "reason": reason, "event": new_event}

        raise SimulationError(f"Acción desconocida: '{action}'.")


SPEC = SimulationSpec(
    slug="processes",
    title="Ciclo de vida de procesos",
    description="Estados y transiciones de procesos.",
    icon="cpu",
    factory=ProcessLifecycleSimulation,
)
