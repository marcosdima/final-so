"""
Registro de simulaciones (el "catálogo" del marco).

Cada simulación se publica mediante una `SimulationSpec` (definida en `core.spec`)
que describe sus metadatos y expone un `factory` capaz de construir una instancia
a partir de una semilla.

El registro es **explícito**: las specs se importan y registran al final de este
módulo (ver `design.md` D2). Añadir una simulación nueva = crear su app + añadir
una línea aquí.
"""

from __future__ import annotations

from core.spec import Simulation, SimulationSpec

# Catálogo global: slug -> spec.
SIMULATIONS: dict[str, SimulationSpec] = {}


def register(spec: SimulationSpec) -> SimulationSpec:
    """Registra una spec. El slug debe ser único."""
    if spec.slug in SIMULATIONS:
        raise ValueError(f"La simulación '{spec.slug}' ya está registrada.")
    SIMULATIONS[spec.slug] = spec
    return spec


def get(slug: str) -> SimulationSpec | None:
    """Devuelve la spec registrada con ese slug, o None."""
    return SIMULATIONS.get(slug)


def all_specs() -> list[SimulationSpec]:
    """Devuelve todas las specs registradas en orden de registro."""
    return list(SIMULATIONS.values())


__all__ = [
    "SIMULATIONS",
    "Simulation",
    "SimulationSpec",
    "all_specs",
    "get",
    "register",
]


# ---------------------------------------------------------------------------
# Registro explícito de las simulaciones del proyecto.
# Se importan aquí para que el catálogo quede poblado al cargar `core`.
# ---------------------------------------------------------------------------
from inodes.simulation import SPEC as _INODES_SPEC
from processes.simulation import SPEC as _PROCESSES_SPEC

register(_INODES_SPEC)
register(_PROCESSES_SPEC)
