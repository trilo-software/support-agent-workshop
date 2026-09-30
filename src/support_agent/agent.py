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

from dataclasses import dataclass, field

from .model import chat
from .document_validation import formatear_informe
from .prompts import SYSTEM_PROMPT
from .rag import RetrievedChunk, retrieve
from .tools import DOCUMENT_TOOLS, TOOLS

MAX_TURNS = 3


@dataclass
class AgentResult:
    reply: str
    sources: list[dict] = field(default_factory=list)
    tool_calls_made: list[str] = field(default_factory=list)
    validation: dict | None = None


def _format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(no se recuperó ningún documento de la base de conocimiento)"
    return "\n\n".join(f"[{c.title}] ({c.source})\n{c.content}" for c in chunks)


async def run_agent(
    message: str, history: list[dict] | None = None, *, document_data: dict | None = None
) -> AgentResult:
    if document_data is not None:
        # No se envían los datos OCR ni las imágenes a Gemini, al historial
        # normal del chat, a la KB o al servidor MCP.
        report = await DOCUMENT_TOOLS["validar_documentos"].handler(datos=document_data)
        calls = ["validar_documentos"]
        if report["referir_agente"]:
            uncertain = ", ".join(
                item["codigo"] for item in report["verificaciones"]
                if item["estado"] in {"faltante", "no_verificable"}
            )
            ticket = await TOOLS["escalate_to_human"].handler(
                summary=f"Piloto documental: revisión necesaria ({uncertain}). Sin datos personales."
            )
            report["ticket_id"] = ticket["ticket_id"]
            calls.append("escalate_to_human")
        return AgentResult(
            reply=formatear_informe(report),
            tool_calls_made=calls,
            validation=report,
        )

    chunks = await retrieve(message)
    sources = [
        {"title": c.title, "source": c.source, "score": round(c.score, 3)}
        for c in chunks
    ]

    system = f"{SYSTEM_PROMPT}\n\nCONTEXTO:\n{_format_context(chunks)}"
    messages: list[dict] = [{"role": "system", "content": system}]
    for msg in history or []:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    tool_calls_made: list[str] = []
    for _ in range(MAX_TURNS):
        reply = await chat(messages, TOOLS)
        if not reply.tool_calls:
            return AgentResult(
                reply=reply.text or "", sources=sources, tool_calls_made=tool_calls_made
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
                result = await tool.handler(**tc.args)
            tool_calls_made.append(tc.name)
            messages.append({"role": "tool", "name": tc.name, "content": result})

    return AgentResult(
        reply="Lo siento, no logré completar la consulta. ¿Puedes intentar de nuevo?",
        sources=sources,
        tool_calls_made=tool_calls_made,
    )
