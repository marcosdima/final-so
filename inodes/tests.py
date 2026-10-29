"""
Pruebas de la simulación de inodos y disco físico fragmentado.
"""

import json

from django.test import Client, TestCase
from django.urls import reverse

from core.exceptions import SimulationError

from .simulation import InodeSimulation


class InodeResolutionTests(TestCase):
    def setUp(self):
        self.sim = InodeSimulation(seed=1234)
        self.client = Client()

    def test_direct_pointer_position_10(self):
        """Posición 10 ➜ Bloque Lógico 9 ➜ Puntero Directo [9]."""
        result = self.sim.resolve_position(10)
        self.assertEqual(result["logical_position"], 10)
        self.assertEqual(result["logical_block_index"], 9)
        self.assertEqual(result["route_type"], "DIRECT")
        self.assertEqual(result["physical_block"], self.sim.direct_blocks[9])
        self.assertEqual(result["pointer_label"], "Directo [9]")

    def test_direct_pointer_position_1(self):
        result = self.sim.resolve_position(1)
        self.assertEqual(result["route_type"], "DIRECT")
        self.assertEqual(result["physical_block"], self.sim.direct_blocks[0])

    def test_indirect_simple_position_14(self):
        result = self.sim.resolve_position(14)
        self.assertEqual(result["route_type"], "INDIRECT_SIMPLE")
        self.assertEqual(result["physical_block"], self.sim.indirect_simple_entries[1])
        self.assertEqual(result["index_block"], self.sim.indirect_simple_block_id)
        self.assertEqual(result["table_index"], 1)

    def test_indirect_double_position_18(self):
        result = self.sim.resolve_position(18)
        self.assertEqual(result["route_type"], "INDIRECT_DOUBLE")
        self.assertIsNotNone(result["physical_block"])

    def test_indirect_triple_position_26(self):
        result = self.sim.resolve_position(26)
        self.assertEqual(result["route_type"], "INDIRECT_TRIPLE")
        self.assertIsNotNone(result["physical_block"])

    def test_resolve_position_out_of_range(self):
        with self.assertRaises(SimulationError):
            self.sim.resolve_position(0)
        with self.assertRaises(SimulationError):
            self.sim.resolve_position(self.sim.total_logical_positions + 1)

    def test_resolve_position_invalid_type(self):
        with self.assertRaises(SimulationError):
            self.sim.resolve_position("10")  # type: ignore[arg-type]

    def test_addresses_unique(self):
        all_blocks = (
            list(self.sim.direct_blocks)
            + [self.sim.indirect_simple_block_id]
            + list(self.sim.indirect_simple_entries)
            + [self.sim.indirect_double_block_id]
            + list(self.sim.indirect_double_l1_entries)
            + [b for v in self.sim.indirect_double_l2_map.values() for b in v]
            + [self.sim.indirect_triple_block_id]
            + list(self.sim.indirect_triple_l1_entries)
            + list(self.sim.indirect_triple_l2_entries)
            + list(self.sim.indirect_triple_data_blocks)
        )
        self.assertEqual(len(all_blocks), len(set(all_blocks)))

    def test_deterministic_with_seed(self):
        a = InodeSimulation(seed=7)
        b = InodeSimulation(seed=7)
        self.assertEqual(a.direct_blocks, b.direct_blocks)
        self.assertEqual(a.get_state(), b.get_state())

    def test_get_state_shape(self):
        state = self.sim.get_state()
        self.assertEqual(state["meta"]["slug"], "inodes")
        self.assertEqual(state["meta"]["seed"], 1234)
        self.assertEqual(state["total_blocks"], 100)
        self.assertEqual(len(state["disk_blocks"]), 100)

    def test_dispatch_resolve(self):
        result = self.sim.dispatch("resolve", {"pos": 10})
        self.assertEqual(result["route_type"], "DIRECT")

    def test_dispatch_unknown_action(self):
        with self.assertRaises(SimulationError):
            self.sim.dispatch("nope", {})


class InodeApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_index_view_status(self):
        response = self.client.get(reverse("inodes:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dark-theme")
        self.assertContains(response, "INODO #42")
        self.assertContains(response, "disk-matrix-100")

    def test_index_view_with_seed(self):
        response = self.client.get(reverse("inodes:index"), {"seed": 99})
        self.assertEqual(response.status_code, 200)

    def test_action_resolve(self):
        response = self.client.post(
            reverse("inodes:action_api"),
            data=json.dumps({"seed": 1234, "action": "resolve", "payload": {"pos": 10}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["result"]["logical_position"], 10)
        self.assertIn("state", data)
        self.assertIn("substructures", data["result"])
        self.assertIn("steps", data["result"])

    def test_action_resolve_out_of_range_400(self):
        response = self.client.post(
            reverse("inodes:action_api"),
            data=json.dumps({"seed": 1, "action": "resolve", "payload": {"pos": 0}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_action_randomize_changes_seed(self):
        response = self.client.post(
            reverse("inodes:action_api"),
            data=json.dumps({"seed": 5, "action": "randomize", "payload": {"seed": 777}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["result"]["seed"], 777)
        self.assertEqual(data["state"]["meta"]["seed"], 777)
