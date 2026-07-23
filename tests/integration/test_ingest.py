"""Idempotencia de la ingesta: archivos sin cambios no se re-embeben."""

from pathlib import Path

from support_agent.ingest import ingest_kb

DOC_A = "# Envíos de prueba\n\n## Tiempos\n\nEl envío tarda dos días.\n"
DOC_B = "# Pagos de prueba\n\n## Métodos\n\nAceptamos tarjeta.\n"


def _write_kb(tmp_path: Path) -> Path:
    (tmp_path / "a.md").write_text(DOC_A, encoding="utf-8")
    (tmp_path / "b.md").write_text(DOC_B, encoding="utf-8")
    return tmp_path


async def test_segunda_ingesta_no_reembebe(tmp_path):
    kb = _write_kb(tmp_path)
    first = await ingest_kb(kb)
    assert first["documentos"] == 2
    assert first["ingresados"] == 2
    assert first["chunks_nuevos"] >= 2

    second = await ingest_kb(kb)
    assert second["documentos"] == 2
    assert second["ingresados"] == 0
    assert second["chunks_nuevos"] == 0
    assert second["chunks_totales"] == first["chunks_totales"]


async def test_solo_el_archivo_modificado_se_reingesta(tmp_path):
    kb = _write_kb(tmp_path)
    await ingest_kb(kb)

    (kb / "a.md").write_text(DOC_A + "\nAhora el envío tarda un día.\n", encoding="utf-8")
    result = await ingest_kb(kb)
    assert result["ingresados"] == 1


async def test_archivo_nuevo_se_ingesta(tmp_path):
    kb = _write_kb(tmp_path)
    await ingest_kb(kb)

    (kb / "c.md").write_text("# Promos de prueba\n\nHay descuento.\n", encoding="utf-8")
    result = await ingest_kb(kb)
    assert result["documentos"] == 3
    assert result["ingresados"] == 1
