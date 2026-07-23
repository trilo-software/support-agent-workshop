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
            "Creé el ticket de soporte. Un humano del equipo de Café Pura Vida "
            "te contactará en las próximas 24 horas."
        ),
    }


tool = Tool(
    name="escalate_to_human",
    description=(
        "Escala la conversación a un agente humano de Café Pura Vida creando "
        "un ticket de soporte. Úsalo cuando el cliente lo pida o cuando el "
        "contexto disponible no alcance para resolver el caso."
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
