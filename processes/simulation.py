"""
Lógica de la simulación del ciclo de vida de procesos.

Módulo **puro** (sin Django). Implementa el contrato `Simulation` del marco
(`get_state` + `dispatch`) con un modelo **stateless de event-sourcing**:

- El cliente mantiene el **log de eventos** (la secuencia de transiciones aplicadas).
- El servidor es el único dueño de la máquina de estados: recibe el log completo,
  lo replay determinista y aplica encima el evento nuevo, validando sus precondiciones.

Así se conserva el estado sin memoria de servidor (clave para Render) y, a la vez,
se permite el **control manual**: crear procesos a mano y disparar admit / dispatch /
interrupt / io_wait / io_complete / exit sobre el proceso elegido.

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
class ProcessLifecycleSimulation:
    """Máquina de estados de procesos reconstruible desde un log de eventos."""

    seed: int | None = None
    # Log de eventos aplicados (lo aporta el cliente; el servidor lo replay).
    events: list[dict[str, Any]] = field(default_factory=list)

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
        }
        self._rebuild(list(self.events))

    # ------------------------------------------------------------------
    # Reconstrucción (replay) del estado a partir del log
    # ------------------------------------------------------------------
    def _reset_state(self) -> None:
        self.process_states: dict[int, ProcessState] = {}
        self.ready_queue: list[int] = []
        self.waiting_queue: list[int] = []
        self.running: int | None = None
        self.terminated: list[int] = []
        self.applied_events: list[dict[str, Any]] = []
        self.history: list[dict[str, Any]] = []

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
    # Transiciones (la máquina de estados)
    # ------------------------------------------------------------------
    def _enqueue_ready(self, pid: int) -> None:
        if pid not in self.ready_queue:
            self.ready_queue.append(pid)

    def _handle_create(self, pid: Any) -> tuple[bool, str]:
        if isinstance(pid, bool) or not isinstance(pid, int) or pid < 1:
            return False, "PID inválido."
        if pid in self.process_states:
            return False, f"P{pid} ya existe."
        self.process_states[pid] = ProcessState.NEW
        return True, ""

    def _handle_admit(self, pid: Any) -> tuple[bool, str]:
        if self.process_states.get(pid) != ProcessState.NEW:
            return False, f"P{pid} no esta en NEW."
        self.process_states[pid] = ProcessState.READY
        self._enqueue_ready(pid)
        return True, ""

    def _handle_dispatch(self, pid: Any) -> tuple[bool, str]:
        if self.running is not None:
            return False, "CPU ocupada."
        if self.process_states.get(pid) != ProcessState.READY:
            return False, f"P{pid} no esta en READY."
        if pid not in self.ready_queue:
            return False, f"P{pid} no esta en la cola de listos."
        self.ready_queue.remove(pid)
        self.running = pid
        self.process_states[pid] = ProcessState.RUNNING
        return True, ""

    def _handle_interrupt(self, pid: Any) -> tuple[bool, str]:
        if self.running != pid:
            return False, f"P{pid} no esta en RUNNING."
        self.running = None
        self.process_states[pid] = ProcessState.READY
        self._enqueue_ready(pid)
        return True, ""

    def _handle_io_wait(self, pid: Any) -> tuple[bool, str]:
        if self.running != pid:
            return False, f"P{pid} no esta en RUNNING."
        self.running = None
        self.process_states[pid] = ProcessState.WAITING
        if pid not in self.waiting_queue:
            self.waiting_queue.append(pid)
        return True, ""

    def _handle_io_complete(self, pid: Any) -> tuple[bool, str]:
        if pid not in self.waiting_queue:
            return False, f"P{pid} no esta en WAITING."
        self.waiting_queue.remove(pid)
        self.process_states[pid] = ProcessState.READY
        self._enqueue_ready(pid)
        return True, ""

    def _handle_exit(self, pid: Any) -> tuple[bool, str]:
        if self.running != pid:
            return False, f"P{pid} no esta en RUNNING."
        self.running = None
        self.process_states[pid] = ProcessState.TERMINATED
        if pid not in self.terminated:
            self.terminated.append(pid)
        return True, ""

    def _apply(self, event: dict[str, Any]) -> tuple[bool, str]:
        if not isinstance(event, dict):
            return False, "Evento inválido."
        handler = self._handlers.get(event.get("type"))
        if handler is None:
            return False, f"Evento desconocido: '{event.get('type')}'."
        return handler(event.get("pid"))

    # ------------------------------------------------------------------
    # Contrato Simulation: estado y acciones
    # ------------------------------------------------------------------
    def get_state_snapshot(self) -> dict[str, Any]:
        return {
            # Claves en string para que sea consistente entre Python, JSON y JS
            # (JsonResponse convierte las claves int en string).
            "states": {str(pid): st.value for pid, st in self.process_states.items()},
            "ready_queue": list(self.ready_queue),
            "waiting_queue": list(self.waiting_queue),
            "running": self.running,
            "terminated": list(self.terminated),
        }

    def get_state(self) -> dict[str, Any]:
        return {
            "meta": {"slug": "processes", "seed": self.seed},
            "pids": list(self.process_states.keys()),
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
