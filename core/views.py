"""
Vistas genéricas del marco de simulaciones.

No contienen lógica de simulación (ver `docs/spec.md` C2): sólo resuelven la spec
por `slug`, construyen la simulación con la semilla recibida y delegan en
`get_state()` / `dispatch()`. Las apps de simulación delegan aquí mediante las
fábricas `make_index_view` y `make_action_view`.
"""

from __future__ import annotations

import json
from typing import Any

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .exceptions import SimulationError
from .simulations import all_specs
from .simulations import get as get_spec


def _resolve_spec_or_404(slug: str):
    spec = get_spec(slug)
    if spec is None:
        raise Http404(f"No existe la simulación '{slug}'.")
    return spec


def _parse_seed(raw: Any) -> int | None:
    """Convierte un valor crudo de querystring a int, o None si está vacío."""
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _resolve_action_url(spec) -> str:
    try:
        return reverse(spec.action_url_name)
    except NoReverseMatch:
        return f"/{spec.slug}/api/action/"


def make_index_view(slug: str):
    """Devuelve la vista GET que renderiza la página de una simulación.

    Lee la semilla opcional de `?seed=`. El estado inicial se embebe en la
    plantilla vía `json_script` para que el JS no necesite una llamada extra.
    """

    @require_GET
    def index(request: HttpRequest) -> HttpResponse:
        spec = _resolve_spec_or_404(slug)
        seed = _parse_seed(request.GET.get("seed"))

        sim = spec.create(seed=seed)
        state = sim.get_state()
        action_url = _resolve_action_url(spec)
        if isinstance(state.get("meta"), dict):
            state["meta"]["action_url"] = action_url

        context: dict[str, Any] = {
            "simulation": spec,
            "seed": seed,
            "structure": state,
            "action_url": action_url,
        }
        if spec.context is not None:
            context.update(spec.context(sim, state))

        return render(request, f"{slug}/index.html", context)

    return index


def _parse_body(request: HttpRequest) -> dict[str, Any]:
    try:
        body = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        raise SimulationError("El cuerpo de la petición no es JSON válido.")
    if not isinstance(body, dict):
        raise SimulationError("El cuerpo debe ser un objeto JSON.")
    return body


def make_action_view(slug: str):
    """Devuelve la vista POST que ejecuta una acción sobre una simulación.

    Espera JSON: `{"seed": 42, "action": "resolve", "payload": {...}}`.
    Devuelve `{"state": ..., "result": ...}`. `SimulationError` ⇒ 400.
    """

    @csrf_exempt
    @require_POST
    def action_api(request: HttpRequest) -> JsonResponse:
        spec = _resolve_spec_or_404(slug)

        try:
            body = _parse_body(request)
            action = body.get("action")
            if not action or not isinstance(action, str):
                raise SimulationError("Falta el campo 'action'.")

            payload = body.get("payload") or {}
            if not isinstance(payload, dict):
                raise SimulationError("El campo 'payload' debe ser un objeto.")

            seed = body.get("seed")
            if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
                raise SimulationError("El campo 'seed' debe ser un entero.")

            sim = spec.create(seed=seed)
            result = sim.dispatch(action, payload)
            state = sim.get_state()
            if isinstance(state.get("meta"), dict):
                state["meta"]["action_url"] = _resolve_action_url(spec)
        except SimulationError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        return JsonResponse({"state": state, "result": result})

    return action_api


@require_GET
def landing(request: HttpRequest) -> HttpResponse:
    """Página de inicio: lista dinámicamente todas las simulaciones registradas."""
    return render(request, "core/landing.html", {"simulations": all_specs()})
