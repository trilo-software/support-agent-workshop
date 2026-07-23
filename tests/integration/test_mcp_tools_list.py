"""El servidor MCP expone los 3 tools con schemas válidos (suite normal:
no depende de que el Ejercicio 5 esté resuelto — solo lista, no llama)."""

from mcp.shared.memory import create_connected_server_and_client_session

from support_agent.mcp_server import mcp


async def test_tools_list_expone_los_tres_tools():
    async with create_connected_server_and_client_session(
        mcp._mcp_server, raise_exceptions=True
    ) as session:
        result = await session.list_tools()
        by_name = {t.name: t for t in result.tools}
        assert set(by_name) == {"check_order_status", "escalate_to_human", "buscar_kb"}
        for tool in by_name.values():
            assert tool.description
            assert tool.inputSchema.get("type") == "object"
        assert "order_number" in by_name["check_order_status"].inputSchema["properties"]
        assert "pregunta" in by_name["buscar_kb"].inputSchema["properties"]
