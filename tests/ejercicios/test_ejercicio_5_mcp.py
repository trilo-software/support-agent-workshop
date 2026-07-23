"""EJERCICIO 5 — Exponer el RAG por MCP (src/support_agent/mcp_server.py).

Rojo mientras buscar_kb devuelva []. Ojo: también necesita el Ejercicio 2
resuelto (buscar_kb usa el mismo retrieve()).
"""

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from support_agent.ingest import ingest_kb
from support_agent.mcp_server import mcp

pytestmark = pytest.mark.ejercicio


async def test_buscar_kb_devuelve_chunks():
    await ingest_kb()
    async with create_connected_server_and_client_session(
        mcp._mcp_server, raise_exceptions=True
    ) as session:
        listed = await session.list_tools()
        assert "buscar_kb" in {t.name for t in listed.tools}

        result = await session.call_tool(
            "buscar_kb", {"pregunta": "¿cuánto tarda el envío a Cartago?"}
        )
        chunks = (result.structuredContent or {}).get("result", [])
        assert chunks, "buscar_kb devolvió una lista vacía: completa el TODO."

        primero = chunks[0]
        valores = " ".join(str(v) for v in primero.values())
        assert "kb/envios.md" in valores, (
            "El primer resultado debería referenciar kb/envios.md (la pregunta "
            "es de envíos). ¿Estás devolviendo la fuente de cada chunk?"
        )
