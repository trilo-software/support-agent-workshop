"""Registry de tools del agente.

Un Tool junta cuatro cosas: nombre, descripción (lo que el modelo lee para
decidir usarlo), schema JSON de parámetros y el handler async que lo ejecuta.
El agente solo puede llamar a los tools que estén en TOOLS.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema de los argumentos
    handler: Callable[..., Awaitable[dict]]


from . import check_order_status, escalate_to_human  # noqa: E402

# ────────────────────────── BONUS ────────────────────────────────
# check_order_status ya está implementado (míralo en
# check_order_status.py) pero nadie lo registró, así que el agente
# no puede consultar pedidos. Agrégalo al registry.
# Verifica:  pytest -m ejercicio tests/ejercicios/test_bonus_tool.py
# Prueba en la UI: "¿cómo va mi pedido CR-1003?"
# ─────────────────────────────────────────────────────────────────
TOOLS: dict[str, Tool] = {
    escalate_to_human.tool.name: escalate_to_human.tool,
    # TODO(bonus): registra aquí check_order_status
}
