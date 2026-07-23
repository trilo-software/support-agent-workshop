"""Acceso a datos: Postgres (pgvector) o memoria, detrás de la misma interfaz.

- Con DATABASE_URL seteada usamos Render Postgres + pgvector.
- Sin ella, un backend en memoria: los chunks viven como vectores numpy y la
  similitud coseno se calcula a mano. Así `pytest` y el run local funcionan
  sin instalar Postgres ni pgvector.

El código SQL de retrieval NO vive aquí sino en rag.py (RETRIEVE_SQL), porque
ahí está el Ejercicio 2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from . import config

logger = logging.getLogger(__name__)

# Pedidos ficticios de semilla. El regex del mock (CR-\d+) depende de este
# formato de número de pedido.
SEED_ORDERS: list[tuple[str, str, str, date | None, str]] = [
    ("CR-1001", "Ana Jiménez", "entregado", date(2026, 7, 10), "2x Tarrazú 340 g, tueste medio"),
    ("CR-1002", "Luis Mora", "en_transito", date(2026, 7, 24), "1x Naranjo 900 g, grano entero"),
    ("CR-1003", "María Fernández", "en_transito", date(2026, 7, 23), "1x Caja degustación"),
    ("CR-1004", "Carlos Rodríguez", "preparando", date(2026, 7, 27), "1x Tres Ríos 340 g, molienda fina"),
    ("CR-1005", "Sofía Vargas", "retrasado", date(2026, 7, 20), "3x Tarrazú 340 g, tueste oscuro"),
    ("CR-1006", "Diego Solano", "entregado", date(2026, 7, 8), "Plan Guaria — envío del mes"),
    ("CR-1007", "Laura Castro", "preparando", date(2026, 7, 28), "2x Naranjo 340 g, molienda gruesa"),
    ("CR-1008", "Jorge Brenes", "retrasado", date(2026, 7, 19), "Plan Tucán — envío del mes"),
]

# Sin índice ivfflat/hnsw a propósito: con ~50 chunks el scan secuencial es
# correcto y rapidísimo, y los índices de pgvector piden un mínimo de filas
# para valer la pena. En una KB real con miles de chunks, aquí iría un HNSW.
SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  id           serial PRIMARY KEY,
  source       text UNIQUE NOT NULL,
  title        text NOT NULL,
  content_hash text NOT NULL,
  ingested_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
  id          serial PRIMARY KEY,
  document_id int NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  content     text NOT NULL,
  embedding   vector(768) NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  order_number text PRIMARY KEY,
  customer     text NOT NULL,
  status       text NOT NULL,
  eta          date,
  items        text NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
  id         serial PRIMARY KEY,
  summary    text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
"""


def to_pgvector(vec: list[float]) -> str:
    """asyncpg no conoce el tipo vector; lo pasamos como texto y casteamos
    con ::vector en el SQL. Es lo más simple y evita registrar codecs."""
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


@dataclass
class MemoryChunk:
    content: str
    title: str
    source: str
    embedding: np.ndarray


@dataclass
class MemoryDB:
    """Backend en memoria: mismos métodos que PostgresDB, cero dependencias."""

    is_postgres: bool = False
    documents: dict[str, dict] = field(default_factory=dict)  # source -> {title, hash}
    chunks: list[MemoryChunk] = field(default_factory=list)
    orders: dict[str, dict] = field(default_factory=dict)
    tickets: list[dict] = field(default_factory=list)

    async def migrate(self) -> None:
        for order_number, customer, status, eta, items in SEED_ORDERS:
            self.orders.setdefault(order_number, {
                "order_number": order_number,
                "customer": customer,
                "status": status,
                "eta": eta.isoformat() if eta else None,
                "items": items,
            })

    async def close(self) -> None:
        pass

    async def get_document_hashes(self) -> dict[str, str]:
        return {source: doc["hash"] for source, doc in self.documents.items()}

    async def replace_document(
        self, source: str, title: str, content_hash: str,
        chunk_rows: list[tuple[str, list[float]]],
    ) -> None:
        self.chunks = [c for c in self.chunks if c.source != source]
        self.documents[source] = {"title": title, "hash": content_hash}
        for content, embedding in chunk_rows:
            self.chunks.append(MemoryChunk(
                content=content, title=title, source=source,
                embedding=np.asarray(embedding, dtype=np.float64),
            ))

    async def count_chunks(self) -> int:
        return len(self.chunks)

    def all_chunks(self) -> list[MemoryChunk]:
        return list(self.chunks)

    async def get_order(self, order_number: str) -> dict | None:
        return self.orders.get(order_number)

    async def insert_ticket(self, summary: str) -> int:
        ticket_id = len(self.tickets) + 1
        self.tickets.append({"id": ticket_id, "summary": summary})
        return ticket_id


class PostgresDB:
    """Backend Postgres + pgvector vía asyncpg, SQL a mano (sin ORM)."""

    is_postgres = True

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
        return self._pool

    async def migrate(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)
            await conn.executemany(
                """INSERT INTO orders (order_number, customer, status, eta, items)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (order_number) DO NOTHING""",
                SEED_ORDERS,
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def get_document_hashes(self) -> dict[str, str]:
        pool = await self._get_pool()
        rows = await pool.fetch("SELECT source, content_hash FROM documents")
        return {r["source"]: r["content_hash"] for r in rows}

    async def replace_document(
        self, source: str, title: str, content_hash: str,
        chunk_rows: list[tuple[str, list[float]]],
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn, conn.transaction():
            doc_id = await conn.fetchval(
                """INSERT INTO documents (source, title, content_hash)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (source) DO UPDATE
                     SET title = $2, content_hash = $3, ingested_at = now()
                   RETURNING id""",
                source, title, content_hash,
            )
            await conn.execute("DELETE FROM chunks WHERE document_id = $1", doc_id)
            await conn.executemany(
                """INSERT INTO chunks (document_id, content, embedding)
                   VALUES ($1, $2, $3::vector)""",
                [(doc_id, content, to_pgvector(emb)) for content, emb in chunk_rows],
            )

    async def count_chunks(self) -> int:
        pool = await self._get_pool()
        return await pool.fetchval("SELECT count(*) FROM chunks")

    async def fetch_retrieval(self, sql: str, embedding: list[float], top_k: int) -> list[dict]:
        """Ejecuta el SQL de retrieval (definido en rag.py) contra pgvector."""
        pool = await self._get_pool()
        rows = await pool.fetch(sql, to_pgvector(embedding), top_k)
        return [dict(r) for r in rows]

    async def get_order(self, order_number: str) -> dict | None:
        pool = await self._get_pool()
        row = await pool.fetchrow(
            "SELECT order_number, customer, status, eta, items FROM orders WHERE order_number = $1",
            order_number,
        )
        if row is None:
            return None
        pedido = dict(row)
        pedido["eta"] = pedido["eta"].isoformat() if pedido["eta"] else None
        return pedido

    async def insert_ticket(self, summary: str) -> int:
        pool = await self._get_pool()
        return await pool.fetchval(
            "INSERT INTO tickets (summary) VALUES ($1) RETURNING id", summary
        )


_db: MemoryDB | PostgresDB | None = None


async def get_db() -> MemoryDB | PostgresDB:
    """Singleton del backend activo. Postgres si hay DATABASE_URL, memoria si no."""
    global _db
    if _db is None:
        dsn = config.database_url()
        if dsn:
            _db = PostgresDB(dsn)
            logger.info("db: usando Postgres")
        else:
            _db = MemoryDB()
            logger.info("db: usando backend en memoria (sin DATABASE_URL)")
    return _db


async def reset_db() -> None:
    """Cierra y descarta el backend activo. Lo usan los tests."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
