"""
Excepciones del marco de simulaciones.

`SimulationError` es la única vía por la que una simulación comunica un fallo
de dominio (entrada inválida, parámetro fuera de rango, etc.). La capa HTTP
(`core.views`) la traduce automáticamente a una respuesta 400 con `{"error": ...}`.
"""


class SimulationError(Exception):
    """Error de validación o de dominio dentro de una simulación.

    Se lanza desde la lógica pura (`<app>/simulation.py`) y se convierte en un
    HTTP 400 en la capa de vistas. No debe usarse para errores internos
    inesperados (esos deben propagarse como 500).
    """

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message
