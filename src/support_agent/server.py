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
import asyncio
import logging
import secrets

import uvicorn
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from . import config
from .agent import run_agent
from .db import get_db
from .document_ocr import DocumentReadError, extract_bundle
from .ingest import ingest_kb
from .mcp_server import mcp
from .rag import retrieve
from .review_store import delete_case, get_case, list_cases, save_case

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

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_FILE_BYTES = 22 * 1024 * 1024
MAX_REQUEST_BYTES = 24 * 1024 * 1024
OCR_SEMAPHORE = asyncio.Semaphore(1)


@app.middleware("http")
async def protect_document_pilot(request: Request, call_next):
    if request.url.path.startswith("/api/documents"):
        configured = config.document_pilot_key()
        supplied = request.headers.get("X-Pilot-Key", "")
        if len(configured) < 16:
            return JSONResponse(status_code=503, content={"error": "Piloto documental deshabilitado."})
        if not secrets.compare_digest(configured.encode("utf-8"), supplied.encode("utf-8")):
            return JSONResponse(status_code=401, content={"error": "Clave del piloto inválida."})
        try:
            request_size = int(request.headers.get("content-length", "0"))
        except ValueError:
            request_size = 0
        if request_size > MAX_REQUEST_BYTES:
            return JSONResponse(status_code=413, content={"error": "Adjuntos demasiado grandes."})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    return await call_next(request)


async def _read_pilot_file(upload: UploadFile, role: str) -> tuple[bytes, str]:
    try:
        data = await upload.read(MAX_FILE_BYTES + 1)
    finally:
        await upload.close()
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError(f"{role}: archivo vacío o mayor a 8 MB.")
    if data.startswith(b"%PDF-"):
        kind = "pdf"
    elif data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = "image"
    else:
        raise ValueError(f"{role}: solo se aceptan PDF, JPG y PNG.")
    if role == "formulario" and kind != "pdf":
        raise ValueError("formulario: se requiere un PDF.")
    if role.startswith("cedula_") and kind != "image":
        raise ValueError(f"{role}: se requiere una imagen JPG o PNG.")
    return data, kind


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


@app.post("/api/documents/validate")
async def api_validate_documents(
    formulario: UploadFile = File(...),
    cedula_frente: UploadFile = File(...),
    cedula_reverso: UploadFile = File(...),
    factura: UploadFile = File(...),
    message: str = Form("Validá los documentos adjuntos"),
):
    uploads = {
        "formulario": formulario,
        "cedula_frente": cedula_frente,
        "cedula_reverso": cedula_reverso,
        "factura": factura,
    }
    try:
        files = {role: await _read_pilot_file(file, role) for role, file in uploads.items()}
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})
    if sum(len(data) for data, _ in files.values()) > MAX_TOTAL_FILE_BYTES:
        return JSONResponse(status_code=413, content={"error": "El expediente supera 22 MB."})

    try:
        async with OCR_SEMAPHORE:
            extracted = await asyncio.to_thread(extract_bundle, files)
    except DocumentReadError as exc:
        extracted = {"_ocr_error": str(exc)}
    except Exception:
        logger.exception("error al procesar adjuntos del piloto")
        extracted = {"_ocr_error": "No se pudo comprobar el contenido de los adjuntos."}

    try:
        result = await run_agent(message, document_data=extracted)
    except Exception:
        logger.exception("error al validar expediente del piloto")
        return JSONResponse(status_code=500, content={"error": "No se pudo validar el expediente."})
    report = result.validation or {}
    if report.get("ticket_id"):
        save_case(report["ticket_id"], files, report)
    return {
        "reply": result.reply,
        "sources": result.sources,
        "tool_calls": result.tool_calls_made,
        "validation": report,
    }


@app.get("/api/documents/reviews")
async def api_review_list():
    return {"revisiones": list_cases()}


@app.get("/api/documents/reviews/{ticket_id}")
async def api_review_detail(ticket_id: int):
    case = get_case(ticket_id)
    if case is None:
        return JSONResponse(status_code=404, content={"error": "Revisión no disponible."})
    return {"ticket_id": ticket_id, "validation": case.report,
            "adjuntos": list(case.files)}


@app.get("/api/documents/reviews/{ticket_id}/files/{role}")
async def api_review_file(ticket_id: int, role: str):
    case = get_case(ticket_id)
    if case is None or role not in case.files:
        return JSONResponse(status_code=404, content={"error": "Adjunto no disponible."})
    data, kind = case.files[role]
    media_type = "application/pdf" if kind == "pdf" else (
        "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
    )
    extension = "pdf" if kind == "pdf" else "png" if media_type == "image/png" else "jpg"
    return Response(data, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{role}.{extension}"',
        "Cache-Control": "no-store",
    })


@app.delete("/api/documents/reviews/{ticket_id}")
async def api_review_delete(ticket_id: int):
    if not delete_case(ticket_id):
        return JSONResponse(status_code=404, content={"error": "Revisión no disponible."})
    return {"deleted": True}


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


class _McpSinRedirect:
    """Starlette responde 307 a `POST /mcp` (sin barra) para mandarlo a
    `/mcp/`, y no todos los clientes MCP siguen redirects. Reescribe la ruta
    internamente para que `/mcp` y `/mcp/` sean lo mismo."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") == "/mcp":
            scope["path"] = "/mcp/"
            scope["raw_path"] = b"/mcp/"
        await self.app(scope, receive, send)


app.add_middleware(_McpSinRedirect)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=config.port())


if __name__ == "__main__":
    main()
