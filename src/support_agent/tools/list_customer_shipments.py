"""Tool: listar los envíos de un cliente a partir de su código de cliente."""

from __future__ import annotations

import re

from ..db import get_db
from . import Tool
from .check_shipment_status import ESTADO_LABELS

MAX_ENVIOS = 20  # evita respuestas enormes si un cliente tiene cientos de envíos


def _parse_codigo(codigo_cliente: str | int) -> int | None:
    """Acepta 5, '5', ' 005 ' o 'cliente 5'; devuelve None si no hay un número."""
    if isinstance(codigo_cliente, int):
        return codigo_cliente if codigo_cliente > 0 else None
    solo_digitos = re.sub(r"\D", "", str(codigo_cliente))
    if not solo_digitos:
        return None
    codigo = int(solo_digitos)
    return codigo if codigo > 0 else None


async def handler(codigo_cliente: str | int) -> dict:
    codigo = _parse_codigo(codigo_cliente)
    if codigo is None:
        return {
            "error": (
                f"{codigo_cliente!r} no es un código de cliente válido. "
                "El código de cliente es solo números, por ejemplo 5."
            )
        }

    db = await get_db()
    envios = await db.get_envios_cliente(codigo)
    if not envios:
        return {
            "error": (
                f"No encontré envíos para el código de cliente {codigo}. "
                "Verifica el código e intenta de nuevo."
            )
        }

    # Nota: el código es consecutivo, así que cualquiera podría consultar el de
    # otra persona. Por eso no devolvemos el nombre del cliente, solo rastreo.
    return {
        "codigo_cliente": codigo,
        "total_envios": len(envios),
        "mostrando": min(len(envios), MAX_ENVIOS),
        "envios": [
            {
                "numero_guia": e["envio_id"],
                "estado": e["estado"],
                "fecha_creacion": e["fecha_creacion"],
                "fecha_entrega": e["fecha_entrega"],
                "unidad_actual": e["unidad_descripcion"],
                "codigo_unidad": e["unidad_actual"],
                "mensaje": ESTADO_LABELS.get(e["estado"], ""),
            }
            for e in envios[:MAX_ENVIOS]
        ],
    }


tool = Tool(
    name="list_customer_shipments",
    description=(
        "Lista los envíos de un cliente de Correos de Costa Rica a partir de su "
        "código de cliente (solo números, por ejemplo 5). Devuelve cada número de "
        "guía con su estado, la sucursal donde se encuentra y sus fechas, del más "
        "reciente al más antiguo."
    ),
    parameters={
        "type": "object",
        "properties": {
            "codigo_cliente": {
                "type": "string",
                "description": "Código de cliente numérico, por ejemplo 5",
            }
        },
        "required": ["codigo_cliente"],
    },
    handler=handler,
)