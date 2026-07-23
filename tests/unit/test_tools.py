from support_agent.db import get_db
from support_agent.tools import check_order_status, escalate_to_human


async def _migrated_db():
    db = await get_db()
    await db.migrate()
    return db


async def test_check_order_status_existente():
    await _migrated_db()
    result = await check_order_status.handler(order_number="CR-1003")
    assert result["order_number"] == "CR-1003"
    assert result["status"] == "en_transito"
    assert "error" not in result


async def test_check_order_status_normaliza_el_numero():
    await _migrated_db()
    result = await check_order_status.handler(order_number="  cr-1001 ")
    assert result["order_number"] == "CR-1001"
    assert result["status"] == "entregado"


async def test_check_order_status_no_existente():
    await _migrated_db()
    result = await check_order_status.handler(order_number="CR-9999")
    assert "error" in result
    assert "CR-9999" in result["error"]


async def test_escalate_to_human_crea_ticket():
    db = await _migrated_db()
    result = await escalate_to_human.handler(summary="Cliente pide hablar con humano")
    assert result["ticket_id"] == 1
    assert "humano" in result["mensaje"].lower()
    assert db.tickets[0]["summary"] == "Cliente pide hablar con humano"
