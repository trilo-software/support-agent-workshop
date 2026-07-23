"""RAG: chunking de la KB y retrieval por similitud coseno.

Aquí vive el EJERCICIO 2. El flujo completo es:

    pregunta -> embed() -> retrieve(top_k) -> chunks más parecidos
             -> se inyectan como CONTEXTO en el prompt del agente.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .db import MemoryChunk, get_db
from .embeddings import embed

# Parámetros de chunking. El Ejercicio 4 (experimento B) juega con estos
# valores: prueba 200 y 3000 y mira cómo cambia el score de los evals.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# ────────────────────────── EJERCICIO 2 (a) ──────────────────────────
# Con TOP_K = 0 el agente vuela a ciegas: no recupera NINGÚN chunk
# de la base de conocimiento. Sube el valor (4 funciona bien).
# ─────────────────────────────────────────────────────────────────────
TOP_K = 0

# ────────────────────────── EJERCICIO 2 (b) ──────────────────────────
# A esta query le falta lo más importante: ordenar por similitud.
# pgvector te da el operador <=> (distancia coseno: menor = más
# parecido). Agrega el ORDER BY para traer los chunks MÁS parecidos
# a la pregunta. Pista: ORDER BY c.embedding <=> $1::vector
# (El backend en memoria imita esta query: mientras no tenga ORDER BY,
# tampoco ordena. Un solo fix arregla ambos.)
# Verifica:  pytest -m ejercicio tests/ejercicios/test_ejercicio_2_rag.py
# ─────────────────────────────────────────────────────────────────────
RETRIEVE_SQL = """
    SELECT c.content, d.title, d.source,
           1 - (c.embedding <=> $1::vector) AS score
    FROM chunks c JOIN documents d ON d.id = c.document_id
    LIMIT $2;
"""


@dataclass
class Chunk:
    content: str
    title: str
    source: str


@dataclass
class RetrievedChunk:
    content: str
    title: str
    source: str
    score: float  # similitud coseno, 0–1 (mayor = más parecido)


def chunk_markdown(text: str, source: str) -> list[Chunk]:
    """Parte un markdown en chunks: primero por headers ##, luego por
    párrafos hasta CHUNK_SIZE caracteres con CHUNK_OVERLAP de traslape.

    El título del documento es su primer H1 (línea que empieza con "# ").
    """
    lines = text.splitlines()
    title = source
    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip()
            break

    # Separar en secciones: lo que hay antes del primer ## y cada sección ##.
    sections: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if current:
                sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())

    chunks: list[Chunk] = []
    for section in sections:
        if not section:
            continue
        for piece in _split_section(section):
            chunks.append(Chunk(content=piece, title=title, source=source))
    return chunks


def _split_section(section: str) -> list[str]:
    """Divide una sección en trozos de a lo sumo CHUNK_SIZE caracteres,
    acumulando párrafos y arrastrando CHUNK_OVERLAP caracteres del trozo
    anterior para no cortar ideas por la mitad."""
    if len(section) <= CHUNK_SIZE:
        return [section]

    paragraphs = [p.strip() for p in section.split("\n\n") if p.strip()]
    pieces: list[str] = []
    current = ""
    for para in paragraphs:
        # Un párrafo más grande que CHUNK_SIZE se corta por tamaño.
        while len(para) > CHUNK_SIZE:
            head, para = para[:CHUNK_SIZE], para[CHUNK_SIZE - CHUNK_OVERLAP:]
            if current:
                pieces.append(current)
                current = ""
            pieces.append(head)
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) > CHUNK_SIZE and current:
            pieces.append(current)
            overlap = current[-CHUNK_OVERLAP:]
            current = f"{overlap}\n\n{para}"
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def rank_chunks(
    query_vec: list[float],
    chunks: list[MemoryChunk],
    top_k: int,
    *,
    ordenar: bool = True,
) -> list[RetrievedChunk]:
    """Ranking del backend en memoria: similitud coseno contra cada chunk.

    Los embeddings están L2-normalizados, así que el producto punto ES la
    similitud coseno. Con ordenar=False devuelve los primeros k en orden de
    inserción — exactamente lo que hace la RETRIEVE_SQL sin ORDER BY.
    """
    qv = np.asarray(query_vec, dtype=np.float64)
    results = [
        RetrievedChunk(
            content=c.content,
            title=c.title,
            source=c.source,
            score=float(np.dot(qv, c.embedding)),
        )
        for c in chunks
    ]
    if ordenar:
        results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]


def _sql_ordena_por_similitud() -> bool:
    """El backend en memoria imita el comportamiento de RETRIEVE_SQL: si la
    query no tiene ORDER BY, en memoria tampoco ordenamos. Así el bug del
    Ejercicio 2 (b) se reproduce igual con o sin Postgres, y el mismo fix
    (agregar el ORDER BY al SQL) arregla los dos backends."""
    return "order by" in RETRIEVE_SQL.lower()


async def retrieve(question: str, top_k: int | None = None) -> list[RetrievedChunk]:
    """Devuelve los top_k chunks de la KB más parecidos a la pregunta."""
    k = TOP_K if top_k is None else top_k
    if k <= 0:
        return []

    query_vec = (await embed([question]))[0]
    db = await get_db()

    if db.is_postgres:
        rows = await db.fetch_retrieval(RETRIEVE_SQL, query_vec, k)
        return [
            RetrievedChunk(
                content=r["content"],
                title=r["title"],
                source=r["source"],
                score=float(r["score"]),
            )
            for r in rows
        ]

    return rank_chunks(
        query_vec, db.all_chunks(), k, ordenar=_sql_ordena_por_similitud()
    )
