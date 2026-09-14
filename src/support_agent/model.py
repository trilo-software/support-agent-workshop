"""Cliente de chat: Gemini real o mock determinista, detrás de una interfaz.

Formato interno de mensajes (independiente del proveedor):

    {"role": "system", "content": str}
    {"role": "user", "content": str}
    {"role": "assistant", "content": str}                 # respuesta de texto
    {"role": "assistant", "tool_calls": [ToolCall, ...],  # pedido de tools
     "raw_content": <Content del proveedor> | None}       #   (ver abajo)
    {"role": "tool", "name": str, "content": dict}        # resultado de un tool

Sobre raw_content: los modelos Gemini 3 firman cada pedido de tool con un
`thought_signature` y exigen recibirlo de vuelta en el siguiente turno; si
reconstruimos la parte function_call desde cero, la API responde 400. Por eso
ModelReply conserva el Content original del modelo y el agente lo reenvía tal
cual. El mock no lo necesita (raw_content=None).

El mock es 100 % determinista (mismos mensajes -> misma respuesta) para que
los tests y la demo sin credenciales sean estables.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field

from . import config
from .tools import Tool

logger = logging.getLogger(__name__)

ORDER_NUMBER_RE = re.compile(r"CR-\d+", re.IGNORECASE)


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class ModelReply:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Content original del proveedor cuando hay tool_calls (Gemini 3 exige
    # devolverlo intacto, con sus thought_signature). None en el mock.
    raw_content: object | None = None


async def chat(messages: list[dict], tools: dict[str, Tool]) -> ModelReply:
    """Una vuelta de conversación: devuelve texto o pedidos de tools."""
    if config.use_mock():
        return _chat_mock(messages, tools)
    return await _chat_gemini(messages, tools)


# ──────────────────────────── mock determinista ───────────────────────────


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _context_titles(messages: list[dict]) -> list[str]:
    """Extrae los títulos de las fuentes del bloque CONTEXTO del system
    prompt (líneas con formato "[Título] (kb/archivo.md)")."""
    system = next((m for m in messages if m.get("role") == "system"), None)
    if system is None:
        return []
    titles: list[str] = []
    for match in re.finditer(r"^\[(.+?)\] \(kb/.+?\)$", system.get("content", ""), re.MULTILINE):
        if match.group(1) not in titles:
            titles.append(match.group(1))
    return titles


def _chat_mock(messages: list[dict], tools: dict[str, Tool]) -> ModelReply:
    tool_results = [m for m in messages if m.get("role") == "tool"]
    if tool_results:
        # Ya se ejecutó al menos un tool: responder incorporando su resultado.
        parts = []
        for result in tool_results:
            payload = json.dumps(result.get("content", {}), ensure_ascii=False, sort_keys=True)
            parts.append(f"resultado de {result.get('name')}: {payload}")
        return ModelReply(text="[mock] " + " · ".join(parts))

    last_user = next(
        (m for m in reversed(messages) if m.get("role") == "user"), {"content": ""}
    )
    user_text = last_user.get("content", "")

    order_match = ORDER_NUMBER_RE.search(user_text)
    if order_match and "check_order_status" in tools:
        return ModelReply(tool_calls=[
            ToolCall(name="check_order_status", args={"order_number": order_match.group(0).upper()})
        ])

    normalized = _normalize(user_text)
    if ("hablar con humano" in normalized or "queja" in normalized) and "escalate_to_human" in tools:
        return ModelReply(tool_calls=[
            ToolCall(name="escalate_to_human", args={"summary": user_text[:200]})
        ])

    titles = _context_titles(messages)
    if titles:
        return ModelReply(
            text=f"[mock] Según {', '.join(titles)}: aquí iría la respuesta basada en la KB."
        )
    return ModelReply(
        text="[mock] No tengo contexto de la base de conocimiento para responder."
    )


# ─────────────────────────────── Gemini real ──────────────────────────────


def _to_gemini_contents(messages: list[dict]):
    """Convierte el formato interno al de google-genai (roles user/model)."""
    from google.genai import types

    contents = []
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            continue  # va aparte, como system_instruction
        if role == "user":
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=msg["content"])]))
        elif role == "assistant":
            if msg.get("raw_content") is not None:
                # Turno con tools del modelo real: se reenvía intacto (firmas).
                contents.append(msg["raw_content"])
            elif msg.get("tool_calls"):
                parts = [
                    types.Part(function_call=types.FunctionCall(name=tc.name, args=tc.args))
                    for tc in msg["tool_calls"]
                ]
                contents.append(types.Content(role="model", parts=parts))
            else:
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=msg.get("content", ""))]))
        elif role == "tool":
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_function_response(name=msg["name"], response=msg["content"])],
            ))
    return contents


async def _chat_gemini(messages: list[dict], tools: dict[str, Tool]) -> ModelReply:
    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=config.gemini_api_key())
    system = next((m["content"] for m in messages if m.get("role") == "system"), None)

    declarations = [
        types.FunctionDeclaration(
            name=t.name, description=t.description, parameters_json_schema=t.parameters
        )
        for t in tools.values()
    ]
    gen_config = types.GenerateContentConfig(
        system_instruction=system,
        tools=[types.Tool(function_declarations=declarations)] if declarations else None,
    )
    contents = _to_gemini_contents(messages)

    for attempt in (1, 2):
        try:
            response = await client.aio.models.generate_content(
                model=config.gemini_model(), contents=contents, config=gen_config
            )
            break
        except errors.ClientError as exc:
            # 429: límite de tasa de Gemini (frecuente con una key compartida
            # entre muchos asistentes). Un retry con backoff y, si persiste,
            # error claro. Escape para el workshop: AGENT_MODEL=mock.
            if getattr(exc, "code", None) == 429 and attempt == 1:
                logger.warning("Gemini devolvió 429; reintentando en 2 s…")
                await asyncio.sleep(2)
                continue
            raise

    if response.function_calls:
        return ModelReply(
            tool_calls=[
                ToolCall(name=fc.name, args=dict(fc.args or {})) for fc in response.function_calls
            ],
            raw_content=response.candidates[0].content,
        )
    return ModelReply(text=response.text or "")
