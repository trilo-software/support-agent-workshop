"""System prompt del agente de soporte. Aquí vive el EJERCICIO 1."""

# ────────────────────────── EJERCICIO 1 ──────────────────────────
# Este system prompt es demasiado pobre: el agente no sabe quién es,
# no usa el CONTEXTO que le pasamos, no cita fuentes y no sabe cuándo
# escalar. Reescríbelo. Tu prompt debe lograr que el agente:
#   1. Se presente como agente de soporte de Café Pura Vida, en español.
#   2. Responda SOLO con información del bloque CONTEXTO.
#   3. Cite la fuente entre corchetes, p. ej. [Envíos].
#   4. Si el contexto no alcanza, lo admita y ofrezca escalar a un humano.
# Verifica:  pytest -m ejercicio tests/ejercicios/test_ejercicio_1_prompt.py
# ─────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = "Eres un asistente."
