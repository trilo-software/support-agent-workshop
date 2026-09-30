"""Tool interno: aplica reglas al expediente ya extraído por OCR local."""

from __future__ import annotations

from ..document_validation import validar_expediente
from . import Tool


async def handler(datos: dict) -> dict:
    return validar_expediente(datos)


tool = Tool(
    name="validar_documentos",
    description=(
        "Valida de forma determinista un formulario aduanero, las dos caras de "
        "la cédula y una factura. Es un tool privado del piloto: nunca se "
        "publica por MCP ni se pasa como función al modelo."
    ),
    parameters={
        "type": "object",
        "properties": {"datos": {"type": "object", "description": "Campos extraídos localmente"}},
        "required": ["datos"],
    },
    handler=handler,
)
