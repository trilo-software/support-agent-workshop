"""BONUS — Registrar check_order_status (src/support_agent/tools/__init__.py).

Rojo mientras el tool no esté en el registry TOOLS.
"""

import pytest

from support_agent.agent import run_agent
from support_agent.db import get_db
from support_agent.tools import TOOLS

pytestmark = pytest.mark.ejercicio


def test_esta_registrado():
    assert "check_order_status" in TOOLS, (
        "El tool existe pero nadie lo registró: agrégalo a TOOLS."
    )


async def test_el_agente_consulta_pedidos():
    db = await get_db()
    await db.migrate()
    result = await run_agent("¿cómo va mi pedido CR-1003?")
    assert "check_order_status" in result.tool_calls_made
    assert "en_transito" in result.reply, (
        "La respuesta debería incorporar el estado del pedido CR-1003."
    )
