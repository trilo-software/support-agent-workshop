"""Tool: cotizar un envío (zona, costo y plazo). Aquí vive el EJERCICIO 5.

Un tool son tres cosas: una DESCRIPCIÓN (lo que el modelo lee para decidir
usarlo), un SCHEMA JSON de parámetros (lo que el modelo tiene que extraer
del mensaje del cliente) y un HANDLER (código determinista que hace el
trabajo). La regla de oro: el modelo extrae los argumentos; el precio y el
plazo los decide el código, nunca el modelo.

Las reglas son las de kb/envios.md:

  Zona GAM        → ₡1.800 · 1 a 2 días hábiles
  Zona Regional   → ₡2.500 · 2 a 3 días hábiles
  Zona Extendida  → ₡3.200 · 3 a 5 días hábiles
  Envío gratis en pedidos superiores a ₡25.000, a cualquier zona.
"""

from __future__ import annotations

import unicodedata

from . import Tool

# Tabla cantón/lugar → zona (simplificada respecto a kb/envios.md). Las
# claves van en minúsculas y sin tildes: usa _normalizar() antes de buscar.
ZONAS: dict[str, str] = {
    "san jose": "GAM", "heredia": "GAM", "alajuela": "GAM", "cartago": "GAM",
    "cartago centro": "GAM", "escazu": "GAM", "curridabat": "GAM", "santa ana": "GAM",
    "grecia": "Regional", "san ramon": "Regional", "turrialba": "Regional",
    "puriscal": "Regional", "cartago rural": "Regional", "atenas": "Regional",
    "limon": "Extendida", "puntarenas": "Extendida", "guanacaste": "Extendida",
    "liberia": "Extendida", "nicoya": "Extendida", "san carlos": "Extendida",
    "upala": "Extendida", "los chiles": "Extendida", "perez zeledon": "Extendida",
    "golfito": "Extendida", "quepos": "Extendida",
}

TARIFAS: dict[str, dict] = {
    "GAM": {"costo": 1800, "dias_habiles": "1 a 2"},
    "Regional": {"costo": 2500, "dias_habiles": "2 a 3"},
    "Extendida": {"costo": 3200, "dias_habiles": "3 a 5"},
}

ENVIO_GRATIS_DESDE = 25_000  # colones; "superiores a ₡25.000"


def _normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni espacios sobrantes: "Limón " -> "limon"."""
    sin_tildes = "".join(
        ch for ch in unicodedata.normalize("NFD", texto) if unicodedata.category(ch) != "Mn"
    )
    return " ".join(sin_tildes.lower().split())


# ────────────────────────── EJERCICIO 5 (a) ──────────────────────────
# Completa el handler. Debe devolver un dict con:
#   canton, zona, costo (0 si aplica envío gratis), envio_gratis (bool),
#   dias_habiles
# y, si el cantón no está en ZONAS, un dict {"error": "..."} explicando qué
# zonas existen (el modelo usa ese texto para responderle al cliente).
# ─────────────────────────────────────────────────────────────────────
async def handler(canton: str, monto_pedido: int) -> dict:
    if monto_pedido < 0:
        return {"error": "El monto del pedido no puede ser negativo."}

    zona = ZONAS.get(_normalizar(canton))
    if zona is None:
        return {
            "error": (
                f"No conozco el cantón {canton!r}. Zonas de envío: GAM "
                "(San José, Heredia, Alajuela centro y Cartago centro), "
                "Regional (resto de Alajuela y Cartago, Grecia, San Ramón, "
                "Turrialba y Puriscal) y Extendida (Limón, Puntarenas, "
                "Guanacaste, Zona Sur y Zona Norte). Pregunta al cliente por "
                "su cantón."
            )
        }

    tarifa = TARIFAS[zona]
    gratis = monto_pedido > ENVIO_GRATIS_DESDE
    return {
        "canton": canton,
        "zona": zona,
        "costo": 0 if gratis else tarifa["costo"],
        "envio_gratis": gratis,
        "dias_habiles": tarifa["dias_habiles"],
    }


# ────────────────────────── EJERCICIO 5 (b) ──────────────────────────
# Completa el tool: la descripción (¿cuándo debe usarlo el modelo? ¿qué
# devuelve?) y el schema de parámetros (canton: string, monto_pedido:
# integer en colones; ambos requeridos, cada uno con su description).
# Fíjate en check_order_status.py: es el mismo patrón.
# Luego regístralo en TOOLS (tools/__init__.py).
# Verifica:  uv run pytest -m ejercicio tests/ejercicios/test_ejercicio_5_tool_propio.py
# ─────────────────────────────────────────────────────────────────────
tool = Tool(
    name="calcular_envio",
    description=(
        "Cotiza el envío de un pedido de Café Pura Vida a partir del cantón "
        "de entrega y el monto en colones. Devuelve la zona, el costo (o si "
        "es gratis) y los días hábiles. Úsalo cuando el cliente pregunte "
        "cuánto cuesta o cuánto tarda un envío a un lugar concreto."
    ),
    parameters={
        "type": "object",
        "properties": {
            "canton": {
                "type": "string",
                "description": "Cantón o lugar de entrega, por ejemplo Heredia o Limón",
            },
            "monto_pedido": {
                "type": "integer",
                "minimum": 0,
                "description": "Monto del pedido en colones, sin puntos ni símbolos",
            },
        },
        "required": ["canton", "monto_pedido"],
    },
    handler=handler,
)
