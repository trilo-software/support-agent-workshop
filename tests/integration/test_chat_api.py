"""POST /api/chat end-to-end con el mock (sin credenciales, sin Postgres).

TestClient corre el lifespan completo (migrate + seed + ingesta + session
manager del MCP). El session manager del transporte MCP solo puede arrancarse
una vez por proceso, así que compartimos un único cliente por módulo.
"""

import pytest
from fastapi.testclient import TestClient

from support_agent.server import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_chat_responde_con_la_forma_correcta(client):
    res = client.post("/api/chat", json={"message": "¿cuánto tarda el envío?"})
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["reply"], str) and data["reply"]
    assert isinstance(data["sources"], list)
    assert isinstance(data["tool_calls"], list)


def test_chat_sin_mensaje_es_400(client):
    assert client.post("/api/chat", json={}).status_code == 400


def test_chat_acepta_historial(client):
    history = [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "¡Pura vida! ¿En qué te ayudo?"},
    ]
    res = client.post("/api/chat", json={"message": "gracias", "history": history})
    assert res.status_code == 200


def test_debug_search_expone_el_retrieval(client):
    res = client.get("/api/debug/search", params={"q": "envío a Cartago", "k": 3})
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "envío a Cartago"
    assert isinstance(data["results"], list)
    for r in data["results"]:
        assert {"title", "source", "score", "content"} <= set(r)


def test_ui_se_sirve_en_raiz(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Café Pura Vida" in res.text
