"""Servidor MCP de Café Pura Vida. Aquí vive el EJERCICIO 5.

Expone por Model Context Protocol (transporte HTTP streamable, montado en
/mcp de la MISMA app FastAPI) las capacidades que ya construiste: los tools
llaman a los MISMOS handlers que usa el agente. Ese es el punto de MCP: no
reescribes capacidades, las publicas por un protocolo estándar para que
cualquier cliente (Claude Code, Claude Desktop, el MCP Inspector, otro
agente) las consuma.

⚠ El endpoint /mcp queda SIN autenticación para el workshop: es de solo
lectura sobre datos ficticios. En producción se protegería con OAuth o un
token (el SDK de MCP soporta ambos).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .rag import retrieve
from .tools import check_order_status as check_order_status_tool
from .tools import escalate_to_human as escalate_to_human_tool

# stateless_http + json_response: cada request es independiente (no hay
# sesión que se pierda si Render redeploya o el free tier se duerme).
mcp = FastMCP("cafe-pura-vida", stateless_http=True, json_response=True)

# La app montada en /mcp debe servir en su raíz (si no, quedaría /mcp/mcp).
mcp.settings.streamable_http_path = "/"


@mcp.tool(
    description=(
        "Consulta el estado de un pedido de Café Pura Vida a partir de su "
        "número (formato CR-1234). Devuelve estado, fecha estimada y artículos."
    )
)
async def check_order_status(order_number: str) -> dict:
    # Fíjate en el patrón: el tool MCP solo envuelve el handler que el agente
    # ya usa. Cero lógica duplicada.
    return await check_order_status_tool.handler(order_number=order_number)


@mcp.tool(
    description=(
        "Escala un caso a un agente humano de Café Pura Vida creando un "
        "ticket de soporte con un resumen del problema."
    )
)
async def escalate_to_human(summary: str) -> dict:
    return await escalate_to_human_tool.handler(summary=summary)


# ────────────────────────── EJERCICIO 5 ──────────────────────────
# Este tool MCP debería exponer TU retrieval a cualquier cliente MCP
# (Claude Code, Claude Desktop, el MCP Inspector...). Ahora mismo
# devuelve una lista vacía. Complétalo:
#   1. Recupera los chunks:     chunks = await retrieve(pregunta, top_k)
#      (retrieve ya embebe la pregunta por ti — es el MISMO retrieve()
#      que encendiste en el Ejercicio 2.)
#   2. Devuélvelos como lista de dicts con: titulo, fuente, score,
#      contenido.
# Fíjate cómo check_order_status (aquí arriba) envuelve su handler:
# es el mismo patrón. La descripción del tool importa: es lo que el
# cliente MCP lee para decidir cuándo usarlo.
# Verifica:  uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_5_mcp.py
# ─────────────────────────────────────────────────────────────────
@mcp.tool(
    description=(
        "Busca en la base de conocimiento de Café Pura Vida (envíos, "
        "suscripciones, facturación, productos, devoluciones) y devuelve los "
        "fragmentos más relevantes para una pregunta, con fuente y score."
    )
)
async def buscar_kb(pregunta: str, top_k: int = 4) -> list[dict]:
    return []  # TODO
