"""Ingesta idempotente de la base de conocimiento (kb/*.md).

Cada archivo se identifica por su sha256: si no cambió desde la última
ingesta, no se vuelve a chunkear ni a embeber (cero llamadas de embedding
desperdiciadas). Si cambió o es nuevo, se borran sus chunks viejos y se
reemplazan. Corre al arrancar el servidor y vía POST /api/ingest.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from . import config
from .db import get_db
from .embeddings import embed
from .rag import chunk_markdown

logger = logging.getLogger(__name__)


async def ingest_kb(kb_dir: Path | str | None = None) -> dict:
    kb_path = Path(kb_dir) if kb_dir is not None else config.KB_DIR
    db = await get_db()
    known_hashes = await db.get_document_hashes()

    total = 0
    ingested = 0
    new_chunks = 0
    for path in sorted(kb_path.glob("*.md")):
        total += 1
        text = path.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        source = f"kb/{path.name}"
        if known_hashes.get(source) == content_hash:
            continue  # sin cambios: no re-embeber

        chunks = chunk_markdown(text, source)
        if not chunks:
            continue
        vectors = await embed([c.content for c in chunks])
        await db.replace_document(
            source,
            chunks[0].title,
            content_hash,
            list(zip((c.content for c in chunks), vectors)),
        )
        ingested += 1
        new_chunks += len(chunks)

    summary = {
        "documentos": total,
        "ingresados": ingested,
        "chunks_nuevos": new_chunks,
        "chunks_totales": await db.count_chunks(),
    }
    logger.info(
        "ingesta: %d documentos, %d nuevos o actualizados, %d chunks nuevos",
        total, ingested, new_chunks,
    )
    return summary
