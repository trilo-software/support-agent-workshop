"""EJERCICIO 2 — Encender el RAG (src/support_agent/rag.py).

Rojo mientras TOP_K = 0 (parte a) o RETRIEVE_SQL no ordene por similitud
(parte b: el backend en memoria imita la query, así que el bug se reproduce
sin Postgres).
"""

import pytest

from support_agent import rag
from support_agent.ingest import ingest_kb

pytestmark = pytest.mark.ejercicio


def test_top_k_encendido():
    assert rag.TOP_K >= 1, "Parte (a): con TOP_K = 0 el agente no recupera nada."


async def test_retrieve_devuelve_chunks():
    await ingest_kb()
    chunks = await rag.retrieve("¿cuánto tarda el envío a Cartago?")
    assert chunks, "Parte (a): retrieve() no devolvió ningún chunk."


async def test_retrieve_ordena_por_similitud():
    await ingest_kb()
    chunks = await rag.retrieve("¿cuánto tarda el envío a Cartago?")
    assert chunks and chunks[0].source == "kb/envios.md", (
        "Parte (b): el chunk más parecido a una pregunta de envíos debería "
        "venir de kb/envios.md y de primero. ¿Le falta el ORDER BY a la query?"
    )
    scores = [c.score for c in chunks]
    assert scores == sorted(scores, reverse=True), (
        "Parte (b): los resultados deben venir de mayor a menor similitud."
    )
