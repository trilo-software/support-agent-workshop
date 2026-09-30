"""Tool: escalar la conversación a un humano creando un ticket."""

from __future__ import annotations

from ..db import get_db
from . import Tool


async def handler(summary: str) -> dict:
    db = await get_db()
    ticket_id = await db.insert_ticket(summary.strip())
    return {
        "ticket_id": ticket_id,
        "mensaje": (
            "Creé el ticket de soporte para que un agente humano del equipo "
            "de Café Pura Vida revise el caso."
        ),
    }


tool = Tool(
    name="escalate_to_human",
    description=(
        "Escala la conversación a un agente humano de Café Pura Vida creando "
        "un ticket de soporte. Úsalo cuando el cliente pida explícitamente "
        "hablar con una persona o cuando el caso requiera intervención o "
        "autorización humana después de intentar resolverlo con la base de "
        "conocimiento, las herramientas y los datos disponibles. No lo uses "
        "solo porque falte un dato que se le pueda solicitar al cliente."
    ),
    parameters={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Resumen breve del caso para el agente humano",
            }
        },
        "required": ["summary"],
    },
    handler=handler,
)
