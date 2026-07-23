"""Config global de tests: siempre mock, siempre backend en memoria.

La suite completa corre sin credenciales y sin Postgres.
"""

import asyncio
import os

import pytest

# Antes de importar cualquier módulo de la app: forzar mock y memoria.
os.environ["AGENT_MODEL"] = "mock"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("GEMINI_API_KEY", None)

from support_agent.db import reset_db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    """Cada test arranca con el backend en memoria vacío."""
    asyncio.run(reset_db())
    yield
    asyncio.run(reset_db())
