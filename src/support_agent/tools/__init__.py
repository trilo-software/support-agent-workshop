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


from . import calcular_envio, check_order_status, escalate_to_human  # noqa: E402

# ────────────────────────── EJERCICIO 4 ──────────────────────────
# check_order_status ya está implementado (míralo en
# check_order_status.py) pero nadie lo registró, así que el agente
# no puede consultar pedidos. Agrégalo al registry.
# Verifica:  uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_4_registrar_tool.py
# Prueba en la UI: "¿cómo va mi pedido CR-1003?"
# ─────────────────────────────────────────────────────────────────
# ────────────────────────── EJERCICIO 5 ──────────────────────────
# Tu propio tool: completa calcular_envio.py (descripción, schema y
# handler) y regístralo aquí igual que los otros dos.
# Verifica:  uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_5_tool_propio.py
# ─────────────────────────────────────────────────────────────────
TOOLS: dict[str, Tool] = {
    escalate_to_human.tool.name: escalate_to_human.tool,
    check_order_status.tool.name: check_order_status.tool,
    calcular_envio.tool.name: calcular_envio.tool,

    # TODO(ejercicio 4): registra aquí check_order_status
    # TODO(ejercicio 5): registra aquí calcular_envio
}
