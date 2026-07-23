import numpy as np

from support_agent.embeddings import embed, mock_embedding


def test_determinismo():
    a = mock_embedding("el envío a Cartago tarda tres días")
    b = mock_embedding("el envío a Cartago tarda tres días")
    assert a == b


def test_norma_uno():
    vec = np.asarray(mock_embedding("café de Tarrazú tueste claro"))
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-9


def test_dimension():
    assert len(mock_embedding("hola")) == 768


def test_palabras_compartidas_dan_similitud():
    envio = np.asarray(mock_embedding("cuánto cuesta el envío a Limón"))
    envio_doc = np.asarray(mock_embedding("el costo del envío a Limón es fijo"))
    disjunto = np.asarray(mock_embedding("tueste oscuro para espresso"))
    assert float(envio @ envio_doc) > float(envio @ disjunto)


def test_acentos_no_importan():
    # "envío" y "envio" deben caer en el mismo bucket.
    assert mock_embedding("envío") == mock_embedding("envio")


async def test_embed_usa_mock_sin_credenciales():
    vectors = await embed(["uno", "dos"])
    assert len(vectors) == 2
    assert vectors[0] == mock_embedding("uno")
