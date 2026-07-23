"""Prueba la versión RESUELTA del ranking en memoria (rank_chunks con
ordenar=True), no el estado roto de los ejercicios: esta suite debe estar
verde en el repo recién forkeado."""

import numpy as np

from support_agent.db import MemoryChunk
from support_agent.embeddings import mock_embedding
from support_agent.rag import rank_chunks


def _chunk(text: str, source: str) -> MemoryChunk:
    return MemoryChunk(
        content=text,
        title=source.removeprefix("kb/").removesuffix(".md").capitalize(),
        source=source,
        embedding=np.asarray(mock_embedding(text)),
    )


CHUNKS = [
    _chunk("la política de devoluciones cubre bolsas sin abrir", "kb/devoluciones.md"),
    _chunk("el envío a Cartago tarda tres días hábiles", "kb/envios.md"),
    _chunk("el plan Jaguar cuesta 17900 colones al mes", "kb/suscripciones.md"),
]


def test_ordena_por_similitud_descendente():
    query = mock_embedding("¿cuánto tarda el envío a Cartago?")
    results = rank_chunks(query, CHUNKS, top_k=3, ordenar=True)
    assert results[0].source == "kb/envios.md"
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_respeta_top_k():
    query = mock_embedding("envío a Cartago")
    assert len(rank_chunks(query, CHUNKS, top_k=2, ordenar=True)) == 2
    assert len(rank_chunks(query, CHUNKS, top_k=10, ordenar=True)) == 3


def test_sin_ordenar_devuelve_orden_de_insercion():
    # Documenta el comportamiento «roto» que reproduce el Ejercicio 2 (b):
    # sin ordenamiento, salen los primeros k por orden de inserción.
    query = mock_embedding("envío a Cartago")
    results = rank_chunks(query, CHUNKS, top_k=2, ordenar=False)
    assert [r.source for r in results] == ["kb/devoluciones.md", "kb/envios.md"]
