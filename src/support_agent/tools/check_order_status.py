"""Tool: consultar el estado de un pedido en la tabla orders."""

from __future__ import annotations

from ..db import get_db
from . import Tool

STATUS_LABELS = {
    "preparando": "Estamos preparando tu pedido en el beneficio.",
    "en_transito": "Tu pedido va en camino.",
    "entregado": "Tu pedido ya fue entregado.",
    "retrasado": "Tu pedido está retrasado; lamentamos la demora.",
}


async def handler(order_number: str) -> dict:
    db = await get_db()
    pedido = await db.get_order(order_number.strip().upper())
    if pedido is None:
        return {
            "error": (
                f"No encontré ningún pedido con el número {order_number!r}. "
                "Verifica el formato (por ejemplo CR-1003) e intenta de nuevo."
            )
        }
    return {
        "order_number": pedido["order_number"],
        "customer": pedido["customer"],
        "status": pedido["status"],
        "eta": pedido["eta"],
        "items": pedido["items"],
        "mensaje": STATUS_LABELS.get(pedido["status"], ""),
    }


tool = Tool(
    name="check_order_status",
    description=(
        "Consulta el estado de un pedido de Café Pura Vida a partir de su "
        "número (formato CR-1234). Devuelve estado, fecha estimada y artículos."
    ),
    parameters={
        "type": "object",
        "properties": {
            "order_number": {
                "type": "string",
                "description": "Número de pedido, por ejemplo CR-1003",
            }
        },
        "required": ["order_number"],
    },
    handler=handler,
)
