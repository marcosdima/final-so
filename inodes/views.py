"""
Vistas de la app de inodos.

No contienen lógica de simulación: delegan en las vistas genéricas del marco
(`core.views`), parametrizadas por el slug de esta simulación.
"""

from core.views import make_action_view, make_index_view

index = make_index_view("inodes")
action_api = make_action_view("inodes")
