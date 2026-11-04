"""
Tipos del contrato de simulación.

Este módulo define `Simulation` (protocolo) y `SimulationSpec` (metadatos + fábrica).
No importa de ninguna app de simulación, de modo que las apps pueden importarlo sin
riesgo de ciclos (el catálogo vivo está en `core.simulations`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Simulation(Protocol):
    """Contrato mínimo que toda simulación debe cumplir (ver `docs/spec.md` §6)."""

    def get_state(self) -> dict[str, Any]:
        """Devuelve el estado completo y serializable de la simulación."""
        ...

    def dispatch(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Aplica una acción y devuelve su resultado (el estado se pide aparte)."""
        ...


@dataclass(frozen=True)
class SimulationSpec:
    """Metadatos y fábrica de una simulación registrada."""

    slug: str
    title: str
    description: str
    icon: str
    factory: Callable[..., Simulation]
    # Contexto extra de render (opcional). Recibe (sim, state) y devuelve un dict
    # que se fusiona con el contexto base. Permite que una simulación añada datos
    # de presentación sin que la vista genérica conozca sus detalles.
    context: Callable[[Simulation, dict[str, Any]], dict[str, Any]] | None = None

    def create(self, *, seed: int | None = None, **params: Any) -> Simulation:
        """Construye una instancia de la simulación con la semilla dada."""
        return self.factory(seed=seed, **params)

    @property
    def url_name(self) -> str:
        """Nombre namespaced de su vista principal (para `{% url %}`)."""
        return f"{self.slug}:index"

    @property
    def action_url_name(self) -> str:
        """Nombre namespaced de su endpoint de acciones (para `{% url %}`)."""
        return f"{self.slug}:action_api"
