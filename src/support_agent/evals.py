"""Mini-evals de retrieval. El EJERCICIO 4 corre y experimenta con esto.

Para cada pregunta dorada de evals/preguntas.yaml verifica dos cosas:

  - hit:   ¿la fuente esperada aparece en el top-k del retrieval?
  - hit@1: ¿aparece de PRIMERA?

Uso:
    uv run python -m support_agent.evals
    uv run python -m support_agent.evals --top-k 8

La lección: un RAG no se mejora «a ojo». Sin un número que comparar antes y
después, no sabes si tu cambio de prompt, chunking o top_k ayudó o empeoró.
"""

from __future__ import annotations

import argparse
import asyncio

import yaml

from . import config, rag
from .ingest import ingest_kb
from .rag import retrieve


def load_questions() -> list[dict]:
    with open(config.EVALS_FILE, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


async def run_evals(top_k: int | None = None) -> dict:
    """Corre el set de preguntas doradas y devuelve el resumen."""
    # Asegura la KB ingerida (en memoria si no hay DATABASE_URL).
    await ingest_kb()

    questions = load_questions()
    effective_k = rag.TOP_K if top_k is None else top_k
    hits = 0
    hits_at_1 = 0
    rows: list[dict] = []

    for entry in questions:
        pregunta = entry["pregunta"]
        esperada = entry["fuente_esperada"]
        results = await retrieve(pregunta, top_k=top_k)
        sources = [r.source for r in results]
        hit = esperada in sources
        hit_1 = bool(sources) and sources[0] == esperada
        hits += hit
        hits_at_1 += hit_1
        rows.append({
            "pregunta": pregunta,
            "esperada": esperada,
            "hit": hit,
            "hit_1": hit_1,
            "posicion": sources.index(esperada) + 1 if hit else None,
            "score": round(results[sources.index(esperada)].score, 3) if hit else None,
        })

    return {
        "top_k": effective_k,
        "total": len(questions),
        "hits": hits,
        "hits_at_1": hits_at_1,
        "rows": rows,
    }


def print_report(report: dict) -> None:
    width = max(len(r["pregunta"]) for r in report["rows"]) + 2
    print()
    print(f"{'':2} {'pregunta':<{width}} {'fuente esperada':<22} {'pos':>4} {'score':>6}")
    print("─" * (width + 38))
    for r in report["rows"]:
        mark = "✓" if r["hit"] else "✗"
        star = "★" if r["hit_1"] else " "
        pos = f"{r['posicion']}º" if r["posicion"] else "—"
        score = f"{r['score']:.3f}" if r["score"] is not None else "—"
        print(f"{mark}{star} {r['pregunta']:<{width}} {r['esperada']:<22} {pos:>4} {score:>6}")
    print("─" * (width + 38))
    print(
        f"retrieval: {report['hits']}/{report['total']} hits · "
        f"{report['hits_at_1']}/{report['total']} hit@1 · top_k={report['top_k']}"
    )
    print("(✓ = la fuente esperada apareció en el top-k · ★ = apareció de primera)\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Mini-evals de retrieval")
    parser.add_argument(
        "--top-k", type=int, default=None,
        help="cuántos chunks recuperar por pregunta (default: TOP_K de rag.py)",
    )
    args = parser.parse_args()
    report = await run_evals(top_k=args.top_k)
    print_report(report)


if __name__ == "__main__":
    asyncio.run(main())
