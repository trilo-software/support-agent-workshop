"""Loop del agente: RAG clásico (retrieve-then-generate) + tools.

El flujo por request es siempre el mismo:

  1. Embeber la pregunta del cliente.
  2. Recuperar los TOP_K chunks más parecidos de la KB (rag.retrieve).
  3. Armar el prompt: SYSTEM_PROMPT + bloque CONTEXTO con esos chunks.
  4. Loop: llamar al modelo; si pide tools, ejecutarlos y repetir
     (máximo MAX_TURNS vueltas); si devuelve texto, terminar.

Es RAG «clásico»: SIEMPRE recuperamos antes de llamar al modelo. La variante
retrieval-as-a-tool (el modelo decide cuándo buscar) queda como extensión.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .model import chat
from .prompts import SYSTEM_PROMPT
from .rag import RetrievedChunk, retrieve
from .tools import TOOLS

MAX_TURNS = 3
MAX_HISTORY_MESSAGES = 20
EMPTY_REPLY = "Lo siento, no obtuve una respuesta. ¿Puedes intentar de nuevo?"

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    reply: str
    sources: list[dict] = field(default_factory=list)
    tool_calls_made: list[str] = field(default_factory=list)


def _format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(no se recuperó ningún documento de la base de conocimiento)"
    return "\n\n".join(f"[{c.title}] ({c.source})\n{c.content}" for c in chunks)


def _valid_history(history: list[dict] | None) -> list[dict]:
    """Conserva un contexto breve con los únicos roles aceptados."""
    valid = []
    for msg in history or []:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            valid.append({"role": role, "content": content.strip()})
    return valid[-MAX_HISTORY_MESSAGES:]


def _retrieval_question(message: str, history: list[dict]) -> str:
    """Incluye el contexto reciente para que un seguimiento conserve su intención."""
    recent = [msg["content"] for msg in history if msg["role"] == "user"][-2:]
    return "\n".join([*recent, message])[-2000:]


async def run_agent(message: str, history: list[dict] | None = None) -> AgentResult:
    valid_history = _valid_history(history)
    chunks = await retrieve(_retrieval_question(message, valid_history))
    sources = [
        {"title": c.title, "source": c.source, "score": round(c.score, 3)}
        for c in chunks
    ]

    system = f"{SYSTEM_PROMPT}\n\nCONTEXTO:\n{_format_context(chunks)}"
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(valid_history)
    messages.append({"role": "user", "content": message})

    tool_calls_made: list[str] = []
    for _ in range(MAX_TURNS):
        reply = await chat(messages, TOOLS)
        if not reply.tool_calls:
            return AgentResult(
                reply=(reply.text or "").strip() or EMPTY_REPLY,
                sources=sources,
                tool_calls_made=tool_calls_made,
            )

        messages.append({
            "role": "assistant",
            "tool_calls": reply.tool_calls,
            "raw_content": reply.raw_content,
        })
        for tc in reply.tool_calls:
            tool = TOOLS.get(tc.name)
            if tool is None:
                result = {"error": f"tool desconocido: {tc.name}"}
            else:
                try:
                    result = await tool.handler(**tc.args)
                except Exception:
                    logger.exception("falló el tool %s", tc.name)
                    result = {
                        "error": (
                            "La herramienta falló temporalmente. No inventes un "
                            "resultado; informa el problema y sugiere reintentar."
                        )
                    }
            tool_calls_made.append(tc.name)
            messages.append({"role": "tool", "name": tc.name, "content": result})

    return AgentResult(
        reply="Lo siento, no logré completar la consulta. ¿Puedes intentar de nuevo?",
        sources=sources,
        tool_calls_made=tool_calls_made,
    )
