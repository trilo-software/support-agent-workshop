from support_agent.rag import CHUNK_OVERLAP, CHUNK_SIZE, chunk_markdown

DOC = """# Título del documento

Intro corta antes de la primera sección.

## Primera sección

Contenido breve de la primera sección.

## Segunda sección

Otro contenido breve.
"""


def test_titulo_es_el_primer_h1():
    chunks = chunk_markdown(DOC, "kb/prueba.md")
    assert chunks
    assert all(c.title == "Título del documento" for c in chunks)
    assert all(c.source == "kb/prueba.md" for c in chunks)


def test_parte_por_headers():
    chunks = chunk_markdown(DOC, "kb/prueba.md")
    # Intro + 2 secciones, todas cortas: un chunk por sección.
    assert len(chunks) == 3
    assert chunks[1].content.startswith("## Primera sección")
    assert chunks[2].content.startswith("## Segunda sección")


def _doc_largo() -> str:
    parrafos = "\n\n".join(
        f"Párrafo número {i}: " + ("palabras y más palabras de relleno. " * 8)
        for i in range(12)
    )
    return f"# Doc largo\n\n## Sección enorme\n\n{parrafos}\n"


def test_tamano_maximo():
    chunks = chunk_markdown(_doc_largo(), "kb/largo.md")
    assert len(chunks) > 1
    # El traslape puede empujar un chunk un poco por encima de CHUNK_SIZE,
    # pero nunca más que CHUNK_OVERLAP + el separador de párrafo.
    limite = CHUNK_SIZE + CHUNK_OVERLAP + 2
    assert all(len(c.content) <= limite for c in chunks)


def test_overlap_entre_chunks():
    # El overlap aplica DENTRO de una sección partida en varios trozos:
    # chunks[0] es el H1 (sección propia), chunks[1] y chunks[2] son trozos
    # consecutivos de la sección enorme.
    chunks = chunk_markdown(_doc_largo(), "kb/largo.md")
    assert len(chunks) >= 3
    primero, segundo = chunks[1].content, chunks[2].content
    assert segundo.startswith(primero[-CHUNK_OVERLAP:])
