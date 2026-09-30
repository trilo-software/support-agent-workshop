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
from datetime import date, datetime, timedelta, timezone

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

CR_TZ = timezone(timedelta(hours=-6))  # Costa Rica, sin horario de verano

_S10_PESOS = (8, 6, 4, 2, 3, 5, 9, 7)


def numero_guia(consecutivo: int, servicio: str = "PY") -> str:
    """Arma un número de guía UPU S10: PY + 8 dígitos + dígito verificador + CR."""
    digitos = f"{consecutivo:08d}"
    resto = 11 - sum(int(d) * p for d, p in zip(digitos, _S10_PESOS)) % 11
    verificador = {10: 0, 11: 5}.get(resto, resto)
    return f"{servicio}{digitos}{verificador}CR"


SEED_CLIENTES: list[tuple[int, str]] = [
    (1, "Ana Jiménez"),
    (2, "Luis Mora"),
    (3, "María Fernández"),
    (4, "Carlos Rodríguez"),
    (5, "Sofía Vargas"),
    (6, "Diego Solano"),
]

SEED_UNIDADES: list[tuple[int, str]] = [
    (1003, "SUCURSAL LA CORTE"),
    (1005, "SUCURSAL BARRIO MEXICO"),
    (1007, "SUCURSAL CENTRO COLON"),
    (1011, "SUCURSAL Y GRIEGA"),
    (1155, "SUCURSAL MIGRACION"),
    (1200, "SUCURSAL PAVAS"),
    (1250, "SUCURSAL ESCAZU"),
    (1300, "SUCURSAL HATILLO"),
    (1350, "SUCURSAL SAN SEBASTIAN"),
    (1400, "SUCURSAL ALAJUELITA"),
    (1450, "SUCURSAL ASERRI"),
    (1500, "SUCURSAL ACOSTA"),
    (2010, "SUCURSAL ZAPOTE"),
    (5150, "SUCURSAL SANTA CRUZ"),
    (5353, "SUCURSAL JICARAL"),
]

# (envio_id, codigo_cliente, estado, fecha_creacion, fecha_entrega, unidad_actual)
# fecha_entrega solo tiene valor si el envío ya se entregó.
SEED_ENVIOS: list[tuple[str, int, str, datetime, date | None, int | None]] = [
    ("PY000010864CR", 1, "entregado",   datetime(2026, 9, 2, 9, 15, tzinfo=CR_TZ),   date(2026, 9, 5),  1200),
    ("PY000010878CR", 1, "en_transito", datetime(2026, 9, 26, 14, 0, tzinfo=CR_TZ),  None,              2010),
    ("PY000010881CR", 2, "en_reparto",  datetime(2026, 9, 25, 8, 30, tzinfo=CR_TZ),  None,              1250),
    ("PY000010895CR", 3, "creado",      datetime(2026, 9, 29, 16, 45, tzinfo=CR_TZ), None,              None),
    ("PY000010904CR", 4, "entregado",   datetime(2026, 9, 10, 11, 0, tzinfo=CR_TZ),  date(2026, 9, 14), 1450),
    ("PY000010918CR", 4, "retrasado",   datetime(2026, 9, 18, 10, 20, tzinfo=CR_TZ), None,              5353),
    ("PY000010921CR", 5, "en_transito", datetime(2026, 9, 27, 13, 10, tzinfo=CR_TZ), None,              5150),
    ("PY000010935CR", 5, "en_sucursal", datetime(2026, 9, 22, 9, 0, tzinfo=CR_TZ),   None,              1011),
    ("PY000010949CR", 6, "devuelto",    datetime(2026, 9, 1, 15, 30, tzinfo=CR_TZ),  None,              1003),
    ("PY000010952CR", 6, "entregado",   datetime(2026, 9, 20, 7, 45, tzinfo=CR_TZ),  date(2026, 9, 23), 1300),
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

CREATE TABLE IF NOT EXISTS clientes (
  codigo_cliente integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  nombre         text NOT NULL
);

CREATE TABLE IF NOT EXISTS unidades (
  codigo_unidad integer PRIMARY KEY,
  descripcion   text NOT NULL
);

CREATE TABLE IF NOT EXISTS envios (
  envio_id       text PRIMARY KEY CHECK (envio_id ~ '^[A-Z]{2}[0-9]{9}CR$'),
  codigo_cliente integer NOT NULL REFERENCES clientes(codigo_cliente),
  estado         text NOT NULL,
  fecha_creacion timestamptz NOT NULL DEFAULT now(),
  fecha_entrega  date,
  unidad_actual  integer REFERENCES unidades(codigo_unidad)
);

CREATE INDEX IF NOT EXISTS envios_codigo_cliente_idx ON envios (codigo_cliente);
"""


def to_pgvector(vec: list[float]) -> str:
    """asyncpg no conoce el tipo vector; lo pasamos como texto y casteamos
    con ::vector en el SQL. Es lo más simple y evita registrar codecs."""
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def _fechas_a_texto(envio: dict) -> dict:
    """Postgres devuelve datetime/date; memoria guarda texto ISO. Normalizamos
    a texto para que ambos backends devuelvan lo mismo (igual que eta en get_order)."""
    for campo in ("fecha_creacion", "fecha_entrega"):
        valor = envio.get(campo)
        if valor is not None and not isinstance(valor, str):
            envio[campo] = valor.isoformat()
    return envio


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
    clientes: dict[int, dict] = field(default_factory=dict)
    unidades: dict[int, dict] = field(default_factory=dict)
    envios: dict[str, dict] = field(default_factory=dict)

    async def migrate(self) -> None:
        for order_number, customer, status, eta, items in SEED_ORDERS:
            self.orders.setdefault(order_number, {
                "order_number": order_number,
                "customer": customer,
                "status": status,
                "eta": eta.isoformat() if eta else None,
                "items": items,
            })
        for codigo, nombre in SEED_CLIENTES:
            self.clientes.setdefault(codigo, {"codigo_cliente": codigo, "nombre": nombre})
        for codigo, descripcion in SEED_UNIDADES:
            self.unidades.setdefault(codigo, {"codigo_unidad": codigo, "descripcion": descripcion})
        for envio_id, cliente, estado, creado, entregado, unidad in SEED_ENVIOS:
            self.envios.setdefault(envio_id, {
                "envio_id": envio_id,
                "codigo_cliente": cliente,
                "estado": estado,
                "fecha_creacion": creado.isoformat(),
                "fecha_entrega": entregado.isoformat() if entregado else None,
                "unidad_actual": unidad,
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

    async def get_envio(self, envio_id: str) -> dict | None:
        envio = self.envios.get(envio_id)
        if envio is None:
            return None
        unidad = self.unidades.get(envio["unidad_actual"])
        return {**envio, "unidad_descripcion": unidad["descripcion"] if unidad else None}

    async def get_envios_cliente(self, codigo_cliente: int) -> list[dict]:
        envios = [
            {k: v for k, v in e.items() if k != "codigo_cliente"}
            for e in self.envios.values()
            if e["codigo_cliente"] == codigo_cliente
        ]
        return sorted(envios, key=lambda e: e["fecha_creacion"], reverse=True)


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
            # Orden obligatorio por las FK: clientes y unidades antes que envíos.
            await conn.executemany(
                """INSERT INTO clientes (codigo_cliente, nombre)
                   VALUES ($1, $2) ON CONFLICT (codigo_cliente) DO NOTHING""",
                SEED_CLIENTES,
            )
            await conn.executemany(
                """INSERT INTO unidades (codigo_unidad, descripcion)
                   VALUES ($1, $2) ON CONFLICT (codigo_unidad) DO NOTHING""",
                SEED_UNIDADES,
            )
            await conn.executemany(
                """INSERT INTO envios (envio_id, codigo_cliente, estado,
                                       fecha_creacion, fecha_entrega, unidad_actual)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (envio_id) DO NOTHING""",
                SEED_ENVIOS,
            )
            # La semilla trae codigo_cliente explícito; avanzamos la secuencia
            # para que el próximo cliente nuevo reciba max + 1 (o 1 si está vacía).
            await conn.execute(
                """SELECT setval(pg_get_serial_sequence('clientes', 'codigo_cliente'),
                                 (SELECT coalesce(max(codigo_cliente), 0) + 1 FROM clientes),
                                 false)"""
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

    async def get_envio(self, envio_id: str) -> dict | None:
        pool = await self._get_pool()
        row = await pool.fetchrow(
            """SELECT e.envio_id, e.codigo_cliente, e.estado, e.fecha_creacion,
                      e.fecha_entrega, e.unidad_actual, u.descripcion AS unidad_descripcion
               FROM envios e
               LEFT JOIN unidades u ON u.codigo_unidad = e.unidad_actual
               WHERE e.envio_id = $1""",
            envio_id,
        )
        return _fechas_a_texto(dict(row)) if row else None

    async def get_envios_cliente(self, codigo_cliente: int) -> list[dict]:
        pool = await self._get_pool()
        rows = await pool.fetch(
            """SELECT envio_id, estado, fecha_creacion, fecha_entrega, unidad_actual
               FROM envios WHERE codigo_cliente = $1
               ORDER BY fecha_creacion DESC""",
            codigo_cliente,
        )
        return [_fechas_a_texto(dict(r)) for r in rows]


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