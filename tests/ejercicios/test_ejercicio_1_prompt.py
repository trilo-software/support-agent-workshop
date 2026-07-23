"""EJERCICIO 1 — El system prompt (src/support_agent/prompts.py).

Verificación heurística sobre el texto del prompt (sin llamar a ningún LLM).
"""

import pytest

from support_agent.prompts import SYSTEM_PROMPT

pytestmark = pytest.mark.ejercicio


def _p() -> str:
    return SYSTEM_PROMPT.lower()


def test_tiene_sustancia():
    assert len(SYSTEM_PROMPT) >= 200, (
        "El prompt sigue demasiado corto: dale identidad, reglas y tono al agente."
    )


def test_se_presenta_como_cafe_pura_vida():
    assert "pura vida" in _p(), "El agente debe saber que trabaja para Café Pura Vida."


def test_usa_el_bloque_contexto():
    assert "contexto" in _p(), (
        "El prompt debe ordenar responder SOLO con la información del bloque CONTEXTO."
    )


def test_pide_citar_fuentes():
    assert "fuente" in _p() or "cita" in _p() or "citar" in _p(), (
        "El prompt debe pedir citar la fuente, p. ej. [Envíos]."
    )


def test_sabe_escalar_a_un_humano():
    assert "humano" in _p() or "escalar" in _p(), (
        "El prompt debe indicar qué hacer cuando el contexto no alcanza: "
        "admitirlo y ofrecer escalar a un humano."
    )
