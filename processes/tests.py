"""
Pruebas de la simulación del ciclo de vida de procesos.
"""

import json

from django.test import Client, TestCase
from django.urls import reverse

from core.exceptions import SimulationError

from .simulation import ProcessLifecycleSimulation


class ProcessLifecycleTests(TestCase):
    def setUp(self):
        self.sim = ProcessLifecycleSimulation(seed=1)
        self.client = Client()

    def test_initial_state(self):
        state = self.sim.get_state()
        self.assertIsNone(state["running"])
        self.assertEqual(state["event_index"], 0)
        self.assertEqual(state["total_events"], 14)

    def test_full_run_terminates(self):
        result = self.sim.dispatch("step", {"step": 14})
        self.assertTrue(result["applied"])
        state = self.sim.get_state()
        self.assertEqual(state["event_index"], 14)
        self.assertEqual(len(state["terminated"]), 3)

    def test_step_zero_is_initial(self):
        self.sim.dispatch("step", {"step": 5})
        state = self.sim.dispatch("step", {"step": 0})
        self.assertEqual(state["event_index"], 0)

    def test_step_out_of_range(self):
        with self.assertRaises(SimulationError):
            self.sim.dispatch("step", {"step": 15})

    def test_stateless_deterministic(self):
        a = ProcessLifecycleSimulation(seed=1)
        b = ProcessLifecycleSimulation(seed=1)
        a.dispatch("step", {"step": 6})
        b.dispatch("step", {"step": 6})
        self.assertEqual(a.get_state(), b.get_state())

    def test_structure_api(self):
        response = self.client.get(reverse("processes:index"))
        self.assertEqual(response.status_code, 200)

    def test_action_step_api(self):
        response = self.client.post(
            reverse("processes:action_api"),
            data=json.dumps({"seed": 1, "action": "step", "payload": {"step": 1}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["result"]["applied"])
        self.assertEqual(data["state"]["event_index"], 1)

    def test_action_step_out_of_range_400(self):
        response = self.client.post(
            reverse("processes:action_api"),
            data=json.dumps({"seed": 1, "action": "step", "payload": {"step": 99}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
