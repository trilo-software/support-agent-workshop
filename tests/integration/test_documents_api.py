"""Flujo multipart protegido del piloto, con extracción sustituida por datos ficticios."""

import copy

import httpx
import pytest

from support_agent import agent, server


KEY = "clave-de-prueba-larga-123"
FILES = {
    "formulario": ("formulario.pdf", b"%PDF-muestra", "application/pdf"),
    "cedula_frente": ("frente.jpg", b"\xff\xd8\xfffrente", "image/jpeg"),
    "cedula_reverso": ("reverso.jpg", b"\xff\xd8\xffreverso", "image/jpeg"),
    "factura": ("factura.jpg", b"\xff\xd8\xfffactura", "image/jpeg"),
}


def expediente() -> dict:
    return {
        "formulario": {
            "paginas": 2, "nombre_autorizacion": "Ana María Solís Vega",
            "cedula_autorizacion": "123456789", "envio_autorizacion": "RP123456789MU",
            "nombre_cliente": "Ana María Solís Vega", "cedula_cliente": "123456789",
            "celular": "88889999", "firma_autorizacion": True,
            "exoneracion": "si", "envio_exoneracion": "RP123456789MU",
            "consignado_a": "Ana María Solís Vega", "mercancia": "Zapatos deportivos",
            "firma_exoneracion": True,
        },
        "cedula_frente": {"nombre": "Ana María Solís Vega", "cedula": "123456789"},
        "cedula_reverso": {"cedula": "123456789", "vencimiento": "31122099"},
        "factura": {"nombre_facturacion": "Ana María Solís Vega",
                    "nombre_envio": "Ana María Solís Vega", "total": "8148"},
    }


@pytest.mark.asyncio
async def test_piloto_protegido_y_revision_descargable(monkeypatch):
    monkeypatch.setattr(server.config, "document_pilot_key", lambda: KEY)
    data = expediente()
    data["factura"]["mercancia"] = None
    monkeypatch.setattr(server, "extract_bundle", lambda files: copy.deepcopy(data))

    async def fake_escalate(summary: str) -> dict:
        assert "Ana" not in summary and "123456789" not in summary
        return {"ticket_id": 901}

    monkeypatch.setattr(agent.TOOLS["escalate_to_human"], "handler", fake_escalate)
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        assert (await client.post("/api/documents/validate", files=FILES)).status_code == 401
        response = await client.post(
            "/api/documents/validate", files=FILES, headers={"X-Pilot-Key": KEY}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["validation"]["resultado"] == "requiere_agente"
        assert body["validation"]["ticket_id"] == 901
        assert body["tool_calls"] == ["validar_documentos", "escalate_to_human"]
        assert "Ana María Solís Vega" not in response.text
        headers = {"X-Pilot-Key": KEY}
        pending = await client.get("/api/documents/reviews", headers=headers)
        assert any(item["ticket_id"] == 901 for item in pending.json()["revisiones"])
        detail = await client.get("/api/documents/reviews/901", headers=headers)
        assert set(detail.json()["adjuntos"]) == set(FILES)
        attachment = await client.get(
            "/api/documents/reviews/901/files/formulario", headers=headers
        )
        assert attachment.content == FILES["formulario"][1]
        assert attachment.headers["cache-control"] == "no-store"
        assert (await client.delete("/api/documents/reviews/901", headers=headers)).status_code == 200
        assert (await client.get("/api/documents/reviews/901", headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_piloto_deshabilitado_sin_clave(monkeypatch):
    monkeypatch.setattr(server.config, "document_pilot_key", lambda: "")
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/documents/validate", files=FILES)
    assert response.status_code == 503
