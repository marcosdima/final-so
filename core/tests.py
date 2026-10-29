"""
Pruebas del marco de simulaciones (registro y API genérica).
"""

import json

from django.test import Client, TestCase
from django.urls import reverse

from .simulations import all_specs, get


class RegistryTests(TestCase):
    def test_inodes_and_processes_registered(self):
        self.assertIsNotNone(get("inodes"))
        self.assertIsNotNone(get("processes"))

    def test_all_specs_returns_both(self):
        slugs = {spec.slug for spec in all_specs()}
        self.assertEqual(slugs, {"inodes", "processes"})

    def test_spec_url_name(self):
        self.assertEqual(get("inodes").url_name, "inodes:index")


class LandingTests(TestCase):
    def test_landing_lists_simulations(self):
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inodos y disco")
        self.assertContains(response, "Ciclo de vida de procesos")


class GenericApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_unknown_slug_index_404(self):
        response = self.client.get("/noexiste/")
        self.assertEqual(response.status_code, 404)

    def test_unknown_slug_action_404(self):
        response = self.client.post(
            "/noexiste/api/action/",
            data=json.dumps({"action": "step"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_action_malformed_json_400(self):
        response = self.client.post(
            "/inodes/api/action/",
            data="{not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_action_missing_field_400(self):
        response = self.client.post(
            "/inodes/api/action/",
            data=json.dumps({"payload": {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_action_wrong_method_405(self):
        response = self.client.get("/inodes/api/action/")
        self.assertEqual(response.status_code, 405)

    def test_index_wrong_method_405(self):
        response = self.client.post("/inodes/")
        self.assertEqual(response.status_code, 405)
