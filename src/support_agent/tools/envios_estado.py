"""Tool: consultar el estado de un envío por número de guía (tabla envios)."""

from __future__ import annotations

import re

from ..db import get_db, numero_guia
from . import Tool

GUIA_RE = re.compile(r"^[A-Z]{2}\d{9}CR$")

ESTADO_LABELS = {
    "creado": "La guía fue registrada; el envío aún no ha ingresado a una sucursal.",
    "en_sucursal": "Tu envío está en la sucursal indicada.",
    "en_transito": "Tu envío va en camino entre sucursales.",
    "en_reparto": "Tu envío salió a reparto y llegará pronto.",
    "entregado": "Tu envío ya fue entregado.",
    "retrasado": "Tu envío está retrasado; lamentamos la demora.",
    "devuelto": "Tu envío fue devuelto al remitente.",
}


def _normalizar(guia: str) -> str:
    """Quita espacios y guiones y pasa a mayúsculas: 'py 0000-10864 cr' -> 'PY000010864CR'."""
    return re.sub(r"[\s-]", "", guia).upper()


def _digito_valido(guia: str) -> bool:
    """Verifica el dígito verificador UPU S10 (posición 11)."""
    return numero_guia(int(guia[2:10]), guia[:2]) == guia


async def handler(numero_guia_envio: str) -> dict:
    guia = _normalizar(numero_guia_envio)
    if not GUIA_RE.match(guia):
        return {
            "error": (
                f"{numero_guia_envio!r} no tiene formato de número de guía. "
                "Debe ser 2 letras, 9 dígitos y CR, por ejemplo PY000010864CR."
            )
        }
    if not _digito_valido(guia):
        return {
            "error": (
                f"El número de guía {guia} no es válido (el dígito verificador "
                "no coincide). Revisa que esté bien copiado."
            )
        }

    db = await get_db()
    envio = await db.get_envio(guia)
    if envio is None:
        return {
            "error": (
                f"No encontré ningún envío con la guía {guia}. "
                "Verifica el número e intenta de nuevo."
            )
        }
    # No devolvemos el nombre ni el código del cliente: cualquiera con la
    # guía puede consultar, así que solo exponemos datos de rastreo.
    return {
        "numero_guia": envio["envio_id"],
        "estado": envio["estado"],
        "fecha_creacion": envio["fecha_creacion"],
        "fecha_entrega": envio["fecha_entrega"],
        "unidad_actual": envio["unidad_descripcion"],
        "codigo_unidad": envio["unidad_actual"],
        "mensaje": ESTADO_LABELS.get(envio["estado"], ""),
    }


tool = Tool(
    name="check_shipment_status",
    description=(
        "Rastrea un envío de Correos de Costa Rica a partir de su número de guía "
        "(formato PY000010864CR: 2 letras, 9 dígitos y CR). Devuelve el estado, "
        "la sucursal donde se encuentra, la fecha de creación y la fecha de entrega "
        "si ya fue entregado."
    ),
    parameters={
        "type": "object",
        "properties": {
            "numero_guia_envio": {
                "type": "string",
                "description": "Número de guía, por ejemplo PY000010864CR",
            }
        },
        "required": ["numero_guia_envio"],
    },
    handler=handler,
)