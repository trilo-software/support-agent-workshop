"""Web service del agente de soporte — patrón «naive agent».

⚠ Todo el trabajo del agente pasa DENTRO del request HTTP: el handler de
/api/chat `await`ea el embedding de la pregunta, el retrieval en la base y
el loop completo del modelo con sus tools antes de responder. Es la forma
más simple de construir un agente, y por eso empezamos aquí, pero no escala:

  - Si el modelo tarda más que el timeout del proxy, el cliente ve un error
    aunque el agente siguiera trabajando.
  - Un deploy en medio de un request pierde el trabajo en vuelo.
  - La concurrencia real la limita el proceso web: muchos chats simultáneos
    compiten por el mismo servidor que atiende el resto del tráfico.

El siguiente paso (fuera de este workshop) es sacar el trabajo del request:
una cola + workers, o Render Workflows.
"""

from __future__ import annotations

import contextlib
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from . import config
from .agent import run_agent
from .db import get_db
from .ingest import ingest_kb
from .mcp_server import mcp
from .rag import retrieve

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    db = await get_db()
    await db.migrate()
    await ingest_kb()
    # El transporte HTTP del servidor MCP necesita su session manager activo.
    async with mcp.session_manager.run():
        yield
    await db.close()


app = FastAPI(title="Café Pura Vida — agente de soporte", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.post("/api/chat")
async def api_chat(body: dict):
    """Chat con el agente. El historial va y viene en el body (el server no
    guarda estado de sesión — más simple y didáctico; en producción iría en
    una base o en el cliente autenticado)."""
    message = str(body.get("message", "")).strip()
    if not message:
        return JSONResponse(status_code=400, content={"error": "falta el campo 'message'"})
    history = body.get("history") or []
    try:
        result = await run_agent(message, history)
    except Exception:
        # Nunca filtrar el stack trace ni credenciales al cliente.
        logger.exception("error en /api/chat")
        return JSONResponse(
            status_code=500,
            content={"error": "El agente falló procesando tu mensaje. Intenta de nuevo."},
        )
    return {
        "reply": result.reply,
        "sources": result.sources,
        "tool_calls": result.tool_calls_made,
    }


@app.post("/api/ingest")
async def api_ingest():
    try:
        return await ingest_kb()
    except Exception:
        logger.exception("error en /api/ingest")
        return JSONResponse(status_code=500, content={"error": "la ingesta falló"})


@app.get("/api/debug/search")
async def api_debug_search(q: str, k: int = 4):
    """La lupa del RAG: retrieval crudo, sin agente ni modelo. Útil para ver
    exactamente qué chunks (y con qué score) recibe el prompt."""
    chunks = await retrieve(q, top_k=k)
    return {
        "query": q,
        "top_k": k,
        "results": [
            {"title": c.title, "source": c.source, "score": round(c.score, 3), "content": c.content}
            for c in chunks
        ],
    }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(config.UI_FILE, media_type="text/html")


# Servidor MCP: misma app, mismo deploy, protocolo estándar en /mcp.
app.mount("/mcp", mcp.streamable_http_app())


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=config.port())


if __name__ == "__main__":
    main()
