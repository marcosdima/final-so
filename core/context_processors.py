"""
Context processors globales del marco de simulaciones.

Expone el catálogo de simulaciones registradas (`nav_simulations`) en todas las
plantillas para construir la navegación principal de forma dinámica sin hardcodear
enlaces por app (ver `docs/spec.md` O5).
"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from .simulations import all_specs


def simulations_catalog(request: HttpRequest) -> dict[str, Any]:
    """Inyecta la lista de `SimulationSpec` y el namespace activo de la vista."""
    resolver_match = getattr(request, "resolver_match", None)
    active_namespace = resolver_match.namespace if resolver_match else ""
    return {
        "nav_simulations": all_specs(),
        "active_namespace": active_namespace,
    }
