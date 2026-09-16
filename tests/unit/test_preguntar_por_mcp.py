"""Parseo de la respuesta de la Interactions API (sin llamar a Gemini)."""

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "preguntar_por_mcp.py"
spec = importlib.util.spec_from_file_location("preguntar_por_mcp", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules["preguntar_por_mcp"] = mod
spec.loader.exec_module(mod)

# Forma real de la respuesta (capturada el 16/9/2026), recortada.
DUMP = {
    "status": "completed",
    "output_text": "El pedido CR-1003 va en tránsito; entrega estimada el 23 de julio de 2026.",
    "steps": [
        {"type": "mcp_server_tool_call", "id": "call_1", "name": "cafe_pura_vida:check_order_status",
         "server_name": "cafe_pura_vida", "arguments": {"order_number": "CR-1003"}, "signature": "x"},
        {"call_id": "call_1", "result": {"result": "{\"status\": \"en_transito\"}"}},
        {"type": "thought", "signature": "y"},
        {"type": "model_output", "content": [{"type": "text", "text": "El pedido CR-1003 va en tránsito."}]},
    ],
}


def test_extrae_llamadas_con_resultado_y_texto():
    llamadas, texto = mod.resumir(DUMP)
    assert len(llamadas) == 1
    assert llamadas[0]["tool"] == "check_order_status"
    assert llamadas[0]["argumentos"] == {"order_number": "CR-1003"}
    assert "en_transito" in str(llamadas[0]["resultado"])
    assert texto.startswith("El pedido CR-1003 va en tránsito")


def test_sin_output_text_usa_model_output():
    dump = {k: v for k, v in DUMP.items() if k != "output_text"}
    _, texto = mod.resumir(dump)
    assert texto == "El pedido CR-1003 va en tránsito."


def test_sin_tools_devuelve_lista_vacia():
    llamadas, texto = mod.resumir({"output_text": "Hola", "steps": []})
    assert llamadas == [] and texto == "Hola"
