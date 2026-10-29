"""
Lógica de la simulación del ciclo de vida de procesos.

Módulo **puro** (sin Django): implementa el contrato `Simulation` del marco
(`get_state` + `dispatch`) y es stateless — el estado es una función pura de
`(seed, step)`. Ver `docs/sims/processes/spec.md` para la máquina de estados.
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


DEFAULT_PROCESS_EVENTS: list[dict[str, Any]] = [
    {"type": "admit", "pid": 1, "label": "Admit P1 (New -> Ready)"},
    {"type": "dispatch", "pid": 1, "label": "Dispatch P1 (Ready -> Running)"},
    {"type": "io_wait", "pid": 1, "label": "I/O wait P1 (Running -> Waiting)"},
    {"type": "admit", "pid": 2, "label": "Admit P2 (New -> Ready)"},
    {
        "type": "io_complete",
        "pid": 1,
        "label": "I/O complete P1 (Waiting -> Ready)",
    },
    {"type": "dispatch", "pid": 1, "label": "Dispatch P1 (Ready -> Running)"},
    {"type": "interrupt", "pid": 1, "label": "Interrupt P1 (Running -> Ready)"},
    {"type": "dispatch", "pid": 2, "label": "Dispatch P2 (Ready -> Running)"},
    {"type": "exit", "pid": 2, "label": "Exit P2 (Running -> Terminated)"},
    {"type": "dispatch", "pid": 1, "label": "Dispatch P1 (Ready -> Running)"},
    {"type": "exit", "pid": 1, "label": "Exit P1 (Running -> Terminated)"},
    {"type": "admit", "pid": 3, "label": "Admit P3 (New -> Ready)"},
    {"type": "dispatch", "pid": 3, "label": "Dispatch P3 (Ready -> Running)"},
    {"type": "exit", "pid": 3, "label": "Exit P3 (Running -> Terminated)"},
]


@dataclass
class ProcessLifecycleSimulation:
    """Máquina de estados de procesos reproducible dada una secuencia de pasos."""

    seed: int | None = None
    pids: list[int] = field(default_factory=lambda: [1, 2, 3])

    def __post_init__(self) -> None:
        if self.seed is None:
            self.seed = random.randrange(2**31)
        self.events: list[dict[str, Any]] = [dict(e) for e in DEFAULT_PROCESS_EVENTS]
        self._handlers = {
            "admit": self._handle_admit,
            "dispatch": self._handle_dispatch,
            "interrupt": self._handle_interrupt,
            "io_wait": self._handle_io_wait,
            "io_complete": self._handle_io_complete,
            "exit": self._handle_exit,
        }
        self._reset_state()

    # ------------------------------------------------------------------
    # Estado y replay determinista
    # ------------------------------------------------------------------
    def _reset_state(self) -> None:
        self.states: dict[int, ProcessState] = {
            pid: ProcessState.NEW for pid in self.pids
        }
        self.ready_queue: list[int] = []
        self.waiting_queue: list[int] = []
        self.running: int | None = None
        self.terminated: list[int] = []
        self.event_index: int = 0
        self.history: list[dict[str, Any]] = []

    def _replay_to(self, step: int) -> dict[str, Any]:
        """Reproduce determinista los primeros `step` eventos desde el inicio."""
        self._reset_state()
        last_result: dict[str, Any] = {
            "applied": False,
            "reason": "",
            "event": None,
        }
        for i in range(step):
            event = self.events[i]
            result = self._apply(event)
            self.event_index = i + 1
            last_result = result
        return last_result

    # ------------------------------------------------------------------
    # Transiciones
    # ------------------------------------------------------------------
    def _enqueue_ready(self, pid: int) -> None:
        if pid not in self.ready_queue:
            self.ready_queue.append(pid)

    def _handle_admit(self, pid: int) -> tuple[bool, str]:
        if self.states.get(pid) != ProcessState.NEW:
            return False, f"P{pid} no esta en NEW."
        self.states[pid] = ProcessState.READY
        self._enqueue_ready(pid)
        return True, ""

    def _handle_dispatch(self, pid: int) -> tuple[bool, str]:
        if self.running is not None:
            return False, "CPU ocupada."
        if pid not in self.ready_queue:
            return False, f"P{pid} no esta en Ready."
        self.ready_queue.remove(pid)
        self.running = pid
        self.states[pid] = ProcessState.RUNNING
        return True, ""

    def _handle_interrupt(self, pid: int) -> tuple[bool, str]:
        if self.running != pid:
            return False, f"P{pid} no esta en Running."
        self.running = None
        self.states[pid] = ProcessState.READY
        self._enqueue_ready(pid)
        return True, ""

    def _handle_io_wait(self, pid: int) -> tuple[bool, str]:
        if self.running != pid:
            return False, f"P{pid} no esta en Running."
        self.running = None
        self.states[pid] = ProcessState.WAITING
        if pid not in self.waiting_queue:
            self.waiting_queue.append(pid)
        return True, ""

    def _handle_io_complete(self, pid: int) -> tuple[bool, str]:
        if pid not in self.waiting_queue:
            return False, f"P{pid} no esta en Waiting."
        self.waiting_queue.remove(pid)
        self.states[pid] = ProcessState.READY
        self._enqueue_ready(pid)
        return True, ""

    def _handle_exit(self, pid: int) -> tuple[bool, str]:
        if self.running != pid:
            return False, f"P{pid} no esta en Running."
        self.running = None
        self.states[pid] = ProcessState.TERMINATED
        if pid not in self.terminated:
            self.terminated.append(pid)
        return True, ""

    def _apply(self, event: dict[str, Any]) -> dict[str, Any]:
        handler = self._handlers.get(event["type"])
        if handler is None:
            return {"applied": False, "reason": "Evento desconocido.", "event": event}
        applied, reason = handler(event["pid"])
        result = {"applied": applied, "reason": reason, "event": event}
        if applied:
            self.history.append({"event": event, "state": self.get_state_snapshot()})
        return result

    # ------------------------------------------------------------------
    # Contrato Simulation: estado y acciones
    # ------------------------------------------------------------------
    def get_state_snapshot(self) -> dict[str, Any]:
        return {
            "states": {pid: st.value for pid, st in self.states.items()},
            "ready_queue": list(self.ready_queue),
            "waiting_queue": list(self.waiting_queue),
            "running": self.running,
            "terminated": list(self.terminated),
        }

    def get_state(self) -> dict[str, Any]:
        snapshot = self.get_state_snapshot()
        return {
            "meta": {"slug": "processes", "seed": self.seed},
            "pids": self.pids,
            **snapshot,
            "events": self.events,
            "event_index": self.event_index,
            "total_events": len(self.events),
            "history": self.history,
        }

    def dispatch(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta una acción. Ver `docs/sims/processes/spec.md` §5."""
        if action == "step":
            raw_step = payload.get("step", self.event_index)
            if isinstance(raw_step, bool) or not isinstance(raw_step, int):
                raise SimulationError("El paso debe ser un entero.")
            if raw_step < 0 or raw_step > len(self.events):
                raise SimulationError(
                    f"Paso fuera de rango: debe estar entre 0 y {len(self.events)}."
                )
            result = self._replay_to(raw_step)
            result["event_index"] = self.event_index
            result["total_events"] = len(self.events)
            return result

        raise SimulationError(f"Acción desconocida: '{action}'.")


SPEC = SimulationSpec(
    slug="processes",
    title="Ciclo de vida de procesos",
    description="Estados y transiciones de procesos.",
    icon="cpu",
    factory=ProcessLifecycleSimulation,
)
