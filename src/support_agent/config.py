"""Configuración central.

Todas las variables de entorno se leen aquí y en ningún otro lado. Se leen
con funciones (no constantes de módulo) para que los tests puedan cambiarlas
con monkeypatch sin reimportar nada.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Raíz del repo: src/support_agent/config.py -> src/support_agent -> src -> raíz
REPO_ROOT = Path(__file__).resolve().parents[2]

# Para correr en local: carga <raíz>/.env si existe (copia .env.example). No
# pisa variables que ya estén definidas en el entorno; en Render no hay .env y
# las variables vienen del dashboard.
load_dotenv(REPO_ROOT / ".env")
KB_DIR = REPO_ROOT / "kb"
EVALS_FILE = REPO_ROOT / "evals" / "preguntas.yaml"
UI_FILE = Path(__file__).resolve().parent / "ui" / "chat.html"

# La dimensión de los embeddings está fijada en el schema (vector(768) en
# Postgres). Si la cambias, tienes que migrar la tabla chunks y re-ingestar.
EMBED_DIM = 768


def gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def gemini_model() -> str:
    """Modelo de chat. NUNCA se hardcodea fuera de esta función.

    gemini-2.5-flash ya no está disponible para proyectos nuevos de Google
    (set-2026); los Gemini 3 exigen thought signatures en tool calling (ver
    model.py).
    """
    return os.environ.get("GEMINI_MODEL", "gemini-3.6-flash").strip()


def gemini_embed_model() -> str:
    """Modelo de embeddings (768 dims vía output_dimensionality)."""
    return os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001").strip()


def database_url() -> str:
    """Sin DATABASE_URL, la app usa el backend en memoria."""
    return os.environ.get("DATABASE_URL", "").strip()


def port() -> int:
    return int(os.environ.get("PORT", "3000"))


def use_mock() -> bool:
    """Modo mock determinista: sin API key, o forzado con AGENT_MODEL=mock.

    Es el paracaídas del workshop: todo el sistema (chat, embeddings, evals,
    MCP) funciona offline con modelos falsos pero estables.
    """
    forced = os.environ.get("AGENT_MODEL", "").strip().lower() == "mock"
    return forced or not gemini_api_key()
