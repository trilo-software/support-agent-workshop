"""EJERCICIO 3 — Alimentar la KB (kb/promociones.md).

Rojo hasta que crees el archivo con contenido de verdad. Ojo: la parte de
retrieval también necesita el Ejercicio 2 resuelto.
"""

import re

import pytest

from support_agent import config
from support_agent.ingest import ingest_kb
from support_agent.rag import chunk_markdown, retrieve

pytestmark = pytest.mark.ejercicio

PROMO = config.KB_DIR / "promociones.md"


def test_el_archivo_existe_y_tiene_sustancia():
    assert PROMO.exists(), "Crea kb/promociones.md (Ejercicio 3)."
    text = PROMO.read_text(encoding="utf-8")
    assert re.search(r"^# .+", text, re.MULTILINE), "Le falta un H1 (# Promociones)."
    assert len(text) >= 300, "Dale contenido concreto: descuentos, montos, condiciones."


def test_se_chunkea():
    text = PROMO.read_text(encoding="utf-8")
    assert len(chunk_markdown(text, "kb/promociones.md")) >= 1


async def test_el_retrieval_lo_encuentra():
    await ingest_kb()
    results = await retrieve("¿tienen descuento para la primera compra?", top_k=4)
    assert results and results[0].source == "kb/promociones.md", (
        "La pregunta sobre el descuento de primera compra debería traer "
        "kb/promociones.md de primero. ¿El archivo habla de eso?"
    )
