"""
Pruebas de la simulación del ciclo de vida de procesos (modelo interactivo).
"""

import json

from django.test import Client, TestCase
from django.urls import reverse

from core.exceptions import SimulationError

from .simulation import ProcessLifecycleSimulation


def apply(sim, *events):
    """Aplica una secuencia de eventos válidos y devuelve el último resultado."""
    result = None
    for ev in events:
        result = sim.dispatch("apply", {"events": sim.get_state()["events"], "event": ev})
    return result


class ProcessLifecycleTests(TestCase):
    def setUp(self):
        self.sim = ProcessLifecycleSimulation(seed=1)
        self.client = Client()

    def test_initial_state_is_empty(self):
        state = self.sim.get_state()
        self.assertEqual(state["pids"], [])
        self.assertIsNone(state["running"])
        self.assertEqual(state["events"], [])

    def test_create_process(self):
        result = self.sim.dispatch(
            "apply", {"events": [], "event": {"type": "create", "pid": 1}}
        )
        self.assertTrue(result["applied"])
        state = self.sim.get_state()
        self.assertEqual(state["pids"], [1])
        self.assertEqual(state["states"]["1"], "NEW")

    def test_full_lifecycle_dispatch_exit(self):
        events = [
            {"type": "create", "pid": 1},
            {"type": "admit", "pid": 1},
            {"type": "dispatch", "pid": 1},
            {"type": "exit", "pid": 1},
        ]
        result = apply(self.sim, *events)
        self.assertTrue(result["applied"])
        state = self.sim.get_state()
        self.assertEqual(state["states"]["1"], "TERMINATED")
        self.assertEqual(state["terminated"], [1])
        self.assertIsNone(state["running"])

    def test_interrupt_returns_to_ready(self):
        apply(
            self.sim,
            {"type": "create", "pid": 1},
            {"type": "admit", "pid": 1},
            {"type": "dispatch", "pid": 1},
        )
        result = self.sim.dispatch(
            "apply",
            {
                "events": self.sim.get_state()["events"],
                "event": {"type": "interrupt", "pid": 1},
            },
        )
        self.assertTrue(result["applied"])
        state = self.sim.get_state()
        self.assertEqual(state["states"]["1"], "READY")
        self.assertIn(1, state["ready_queue"])
        self.assertIsNone(state["running"])

    def test_io_wait_and_complete(self):
        apply(
            self.sim,
            {"type": "create", "pid": 1},
            {"type": "admit", "pid": 1},
            {"type": "dispatch", "pid": 1},
            {"type": "io_wait", "pid": 1},
        )
        self.assertEqual(self.sim.get_state()["states"]["1"], "WAITING")
        result = self.sim.dispatch(
            "apply",
            {
                "events": self.sim.get_state()["events"],
                "event": {"type": "io_complete", "pid": 1},
            },
        )
        self.assertTrue(result["applied"])
        self.assertEqual(self.sim.get_state()["states"]["1"], "READY")

    def test_invalid_transition_reports_reason(self):
        # dispatch sin haber admitido ⇒ precondición fallida
        apply(self.sim, {"type": "create", "pid": 1})
        result = self.sim.dispatch(
            "apply",
            {
                "events": self.sim.get_state()["events"],
                "event": {"type": "dispatch", "pid": 1},
            },
        )
        self.assertFalse(result["applied"])
        self.assertIn("reason", result)

    def test_stateless_deterministic(self):
        events = [
            {"type": "create", "pid": 1},
            {"type": "admit", "pid": 1},
            {"type": "dispatch", "pid": 1},
        ]
        a = ProcessLifecycleSimulation(seed=1, events=events)
        b = ProcessLifecycleSimulation(seed=1, events=events)
        self.assertEqual(a.get_state(), b.get_state())

    def test_unknown_action(self):
        with self.assertRaises(SimulationError):
            self.sim.dispatch("nope", {})

    def test_bad_history_raises(self):
        with self.assertRaises(SimulationError):
            ProcessLifecycleSimulation(seed=1, events=[{"type": "dispatch", "pid": 1}])

    def test_scheduler_fcfs_order(self):
        # Crear y admitir P1, P2
        apply(
            self.sim,
            {"type": "create", "pid": 1},
            {"type": "create", "pid": 2},
            {"type": "admit", "pid": 1},
            {"type": "admit", "pid": 2},
        )
        state = self.sim.get_state()
        self.assertEqual(state["next_scheduled"], 1)
        self.assertEqual(state["ready_queue"], [1, 2])
        # Despachar sin especificar PID despacha al primero de la cola (FCFS)
        res = apply(self.sim, {"type": "dispatch"})
        self.assertTrue(res["applied"])
        self.assertEqual(self.sim.get_state()["running"], 1)

    def test_scheduler_priority_order(self):
        # Crear P1 con prioridad baja (3) y P2 con prioridad alta (1)
        apply(
            self.sim,
            {"type": "set_algorithm", "payload": {"algorithm": "PRIORITY"}},
            {"type": "create", "pid": 1, "priority": 3},
            {"type": "create", "pid": 2, "priority": 1},
            {"type": "admit", "pid": 1},
            {"type": "admit", "pid": 2},
        )
        state = self.sim.get_state()
        # En PRIORITY, P2 debe estar primero en la cola por tener prioridad 1
        self.assertEqual(state["ready_queue"], [2, 1])
        self.assertEqual(state["next_scheduled"], 2)

    def test_round_robin_quantum_expiration_via_tick(self):
        apply(
            self.sim,
            {"type": "set_algorithm", "payload": {"algorithm": "RR", "quantum": 2}},
            {"type": "create", "pid": 1, "burst_time": 4},
            {"type": "admit", "pid": 1},
            {"type": "dispatch", "pid": 1},
        )
        # 1er tick
        apply(self.sim, {"type": "tick"})
        self.assertEqual(self.sim.get_state()["running"], 1)
        # 2do tick (alcanza quantum=2): se interrumpe y vuelve a READY
        apply(self.sim, {"type": "tick"})
        state = self.sim.get_state()
        self.assertIsNone(state["running"])
        self.assertEqual(state["states"]["1"], "READY")


class ProcessApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_index_view_status(self):
        response = self.client.get(reverse("processes:index"))
        self.assertEqual(response.status_code, 200)

    def _post(self, payload):
        return self.client.post(
            reverse("processes:action_api"),
            data=json.dumps({"seed": 1, "action": "apply", "payload": payload}),
            content_type="application/json",
        )

    def test_action_create(self):
        response = self._post({"events": [], "event": {"type": "create", "pid": 1}})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["result"]["applied"])
        self.assertEqual(data["state"]["pids"], [1])
        self.assertEqual(len(data["state"]["events"]), 1)

    def test_action_invalid_transition_200_with_reason(self):
        response = self._post(
            {"events": [{"type": "create", "pid": 1}], "event": {"type": "exit", "pid": 1}}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["result"]["applied"])
        self.assertIn("reason", data["result"])

    def test_action_bad_history_400(self):
        response = self._post(
            {"events": [{"type": "exit", "pid": 1}], "event": None}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_action_reset_via_empty_events(self):
        response = self._post({"events": []})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"]["pids"], [])
