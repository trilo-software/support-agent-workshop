"""System prompt del agente de soporte. Aquí vive el EJERCICIO 1."""

# ────────────────────────── EJERCICIO 1 ──────────────────────────
# Este system prompt es demasiado pobre: el agente no sabe quién es,
# no usa el CONTEXTO que le pasamos, no cita fuentes y no sabe cuándo
# escalar. Reescríbelo. Tu prompt debe lograr que el agente:
#   1. Se presente como agente de soporte de Café Pura Vida, en español.
#   2. Responda SOLO con información del bloque CONTEXTO.
#   3. Cite la fuente entre corchetes, p. ej. [Envíos].
#   4. Si el contexto no alcanza, lo admita y ofrezca escalar a un humano.
# Verifica:  uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_1_prompt.py
# ─────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = "Eres un asistente que debe presentarse como el agente de inteligencia artifical de cafe pura vida, debes responder en español y solo con la informacion del bloque CONTEXTO. Cada vez que uses una fuente debes mostrarla entre corchetes, ejemplo [Envios]. Si el contexto no alcanza aavisa y escala a un human."
