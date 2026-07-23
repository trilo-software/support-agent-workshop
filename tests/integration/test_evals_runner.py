"""Humo del runner de evals: corre sin credenciales y produce la forma
correcta. NO fija el score exacto (eso depende del estado de los ejercicios)."""

from support_agent.evals import load_questions, run_evals


def test_preguntas_doradas_bien_formadas():
    questions = load_questions()
    assert len(questions) >= 10
    for q in questions:
        assert q["pregunta"].strip()
        assert q["fuente_esperada"].startswith("kb/")
        assert q["fuente_esperada"].endswith(".md")


async def test_runner_produce_el_formato_correcto():
    report = await run_evals(top_k=4)
    assert report["total"] == len(load_questions())
    assert 0 <= report["hits_at_1"] <= report["hits"] <= report["total"]
    assert report["top_k"] == 4
    for row in report["rows"]:
        assert {"pregunta", "esperada", "hit", "hit_1", "posicion", "score"} <= set(row)
