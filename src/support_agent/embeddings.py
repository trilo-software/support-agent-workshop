"""Embeddings: Gemini real o mock determinista.

El mock usa el «hashing trick»: cada palabra suma 1.0 en una posición fija
del vector derivada de su sha256. Textos que comparten palabras tienen
similitud > 0, así el retrieval funciona (y se puede testear) sin llamar a
ninguna API. Es determinista entre procesos y máquinas: usamos sha256 del
token, no hash() de Python (que se aleatoriza por proceso).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

import numpy as np

from . import config

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(_strip_accents(text.lower()))


def _token_index(token: str) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % config.EMBED_DIM


def mock_embedding(text: str) -> list[float]:
    vec = np.zeros(config.EMBED_DIM, dtype=np.float64)
    for token in _tokenize(text):
        vec[_token_index(token)] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec.tolist()


async def _embed_gemini(texts: list[str]) -> list[list[float]]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.gemini_api_key())
    result = await client.aio.models.embed_content(
        model=config.gemini_embed_model(),
        contents=texts,  # la API acepta batch: un embedding por texto
        config=types.EmbedContentConfig(output_dimensionality=config.EMBED_DIM),
    )
    vectors: list[list[float]] = []
    for emb in result.embeddings:
        vec = np.asarray(emb.values, dtype=np.float64)
        # Con gemini-embedding-001 solo la salida de 3072 dims viene
        # normalizada; a 768 hay que normalizar L2 a mano para que la
        # distancia coseno de pgvector tenga sentido.
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        vectors.append(vec.tolist())
    return vectors


async def embed(texts: list[str]) -> list[list[float]]:
    """Devuelve un vector L2-normalizado de 768 dims por cada texto."""
    if not texts:
        return []
    if config.use_mock():
        return [mock_embedding(t) for t in texts]
    return await _embed_gemini(texts)
