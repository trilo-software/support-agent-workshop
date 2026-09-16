#!/usr/bin/env python3
"""Ejercicio 5, segunda mitad: que OTRO agente use TU servidor MCP.

La API de Gemini se conecta sola a un servidor MCP remoto (Streamable HTTP,
público): le pasas la URL de tu servicio y el modelo decide cuándo llamar
tus tools (buscar_kb, check_order_status, escalate_to_human). Sin Claude,
sin cuentas extra: la misma key de Gemini del workshop.

Uso:
    uv run python scripts/preguntar_por_mcp.py https://<tu-servicio>.onrender.com/mcp
    uv run python scripts/preguntar_por_mcp.py https://<tu-servicio>.onrender.com/mcp "¿cómo va el pedido CR-1003?"

Necesita GEMINI_API_KEY en tu .env (o exportada). El servidor tiene que ser
público: localhost NO sirve, porque quien se conecta es el backend de Gemini,
no tu máquina. El nombre del servidor va en snake_case (sin guiones): es una
regla de la API.
"""

from __future__ import annotations

import json
import sys

from support_agent import config  # carga .env y fija el modelo por defecto

SERVER_NAME = "cafe_pura_vida"
PREGUNTA_DEFAULT = "¿Cuánto tarda un envío de Café Pura Vida a Cartago y cuánto cuesta?"


def resumir(dump: dict) -> tuple[list[dict], str]:
    """Extrae de la respuesta de la API los tools llamados y el texto final.

    Estructura relevante (Interactions API): `steps` con entradas de tipo
    `mcp_server_tool_call` (name «servidor:tool», arguments), su resultado
    (call_id, result), `thought` y `model_output`; y `output_text` con la
    respuesta final ya concatenada.
    """
    llamadas: list[dict] = []
    resultados: dict[str, object] = {}
    for step in dump.get("steps") or []:
        if step.get("type") == "mcp_server_tool_call":
            nombre = str(step.get("name", ""))
            llamadas.append({
                "id": step.get("id"),
                "tool": nombre.split(":", 1)[-1],
                "argumentos": step.get("arguments") or {},
            })
        elif step.get("call_id") is not None and "result" in step:
            resultados[str(step["call_id"])] = step["result"]
    for llamada in llamadas:
        llamada["resultado"] = resultados.get(str(llamada["id"]))

    texto = (dump.get("output_text") or "").strip()
    if not texto:
        for step in dump.get("steps") or []:
            if step.get("type") == "model_output":
                for parte in step.get("content") or []:
                    if parte.get("type") == "text":
                        texto += parte.get("text", "")
    return llamadas, texto.strip()


def preguntar(url: str, pregunta: str) -> dict:
    from google import genai

    client = genai.Client(api_key=config.gemini_api_key())
    interaccion = client.interactions.create(
        model=config.gemini_model(),
        input=pregunta,
        tools=[{"type": "mcp_server", "name": SERVER_NAME, "url": url}],
    )
    return interaccion.model_dump()


def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].startswith("http"):
        print(__doc__)
        raise SystemExit(1)
    url = sys.argv[1]
    pregunta = " ".join(sys.argv[2:]).strip() or PREGUNTA_DEFAULT

    if not config.gemini_api_key():
        raise SystemExit(
            "Falta GEMINI_API_KEY: ponla en tu .env (cp .env.example .env) o expórtala."
        )
    if "localhost" in url or "127.0.0.1" in url:
        raise SystemExit(
            "La API de Gemini no puede llegar a localhost: usa la URL pública de tu servicio en Render."
        )

    print(f"modelo: {config.gemini_model()} · servidor MCP: {url}")
    print(f"pregunta: {pregunta}\n")
    try:
        dump = preguntar(url, pregunta)
    except Exception as exc:  # errores de API: key, cuota, servidor dormido…
        raise SystemExit(
            f"Gemini devolvió un error: {str(exc)[:300]}\n"
            "Pistas: ¿tu servicio está despierto? (abre la URL en el navegador y reintenta) · "
            "¿la URL termina en /mcp? · ¿la key es válida?"
        ) from exc

    llamadas, texto = resumir(dump)
    if not llamadas:
        print("Gemini NO llamó ningún tool de tu servidor. ¿buscar_kb sigue devolviendo []? "
              "¿La descripción del tool explica cuándo usarlo?\n")
    for llamada in llamadas:
        print(f"→ Gemini llamó a tu tool {llamada['tool']} con {json.dumps(llamada['argumentos'], ensure_ascii=False)}")
        if llamada.get("resultado") is not None:
            print(f"← tu servidor respondió: {json.dumps(llamada['resultado'], ensure_ascii=False)[:300]}")
    print(f"\nGemini: {texto or '(sin texto)'}")


if __name__ == "__main__":
    main()
