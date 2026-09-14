"""Conversión de mensajes al formato de google-genai (sin llamar a la API).

Los Gemini 3 exigen devolver intacto el turno del modelo que pidió tools (trae
thought_signature); si se reconstruye desde cero, la API responde 400.
"""

from google.genai import types

from support_agent.model import ToolCall, _to_gemini_contents


def test_reenvia_intacto_el_turno_con_tools_del_modelo_real():
    original = types.Content(
        role="model",
        parts=[types.Part(
            function_call=types.FunctionCall(name="check_order_status", args={"order_number": "CR-1003"}),
            thought_signature=b"firma-opaca",
        )],
    )
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "¿cómo va mi pedido CR-1003?"},
        {"role": "assistant", "tool_calls": [ToolCall("check_order_status", {"order_number": "CR-1003"})],
         "raw_content": original},
        {"role": "tool", "name": "check_order_status", "content": {"status": "en_transito"}},
    ]
    contents = _to_gemini_contents(messages)
    assert contents[1] is original
    assert contents[1].parts[0].thought_signature == b"firma-opaca"
    assert contents[2].parts[0].function_response.name == "check_order_status"


def test_sin_raw_content_reconstruye_la_llamada():
    messages = [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "tool_calls": [ToolCall("escalate_to_human", {"summary": "x"})], "raw_content": None},
    ]
    contents = _to_gemini_contents(messages)
    assert contents[1].role == "model"
    assert contents[1].parts[0].function_call.name == "escalate_to_human"
