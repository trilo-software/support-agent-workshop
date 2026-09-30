"""OCR local y extracción acotada para el formulario aduanero del piloto.

Los archivos nunca se envían al modelo de chat, al RAG ni a MCP. Las reglas
dependen de etiquetas visibles en los cuatro documentos de este trámite.
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rapidocr import RapidOCR

MAX_PAGES = 4
MAX_IMAGE_PIXELS = 20_000_000
OCR_MAX_EDGE = 1000
TRACKING_RE = re.compile(r"\b[A-Z]{2}\s*\d{9}\s*[A-Z]{2}\b", re.IGNORECASE)
ID_RE = re.compile(r"(?<!\d)(?:\d[\s-]*){9}(?!\d)")
PHONE_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")


class DocumentReadError(ValueError):
    """Archivo ilegible, inválido o demasiado grande para el piloto."""


@dataclass(frozen=True)
class OCRLine:
    text: str
    score: float
    y: float  # Coordenada vertical, entre 0 y 1.


@dataclass(frozen=True)
class OCRPage:
    lines: tuple[OCRLine, ...]

    @property
    def texts(self) -> list[str]:
        return [line.text.strip() for line in self.lines if line.text.strip()]


@lru_cache(maxsize=1)
def _engine() -> RapidOCR:
    from rapidocr import RapidOCR

    return RapidOCR(params={
        "Global.use_cls": False,  # Los cuatro documentos se reciben orientados.
        "Global.log_level": "warning",
        "EngineConfig.onnxruntime.intra_op_num_threads": 1,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    })


def _norm(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _read_image(data: bytes, *, max_edge: int = OCR_MAX_EDGE) -> OCRPage:
    from PIL import Image, ImageOps, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise DocumentReadError("La imagen supera el límite de resolución del piloto.")
            image = ImageOps.exif_transpose(image).convert("RGB")
            # Las fotos de móvil suelen medir 12 MP o más. Reducirlas antes de
            # OCR evita picos de memoria incompatibles con el plan free.
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            height = image.height
            result = _engine()(image)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        if isinstance(exc, DocumentReadError):
            raise
        raise DocumentReadError("No se pudo leer la imagen.") from exc

    lines = []
    boxes = result.boxes if result.boxes is not None else ()
    for text, score, box in zip(result.txts or (), result.scores or (), boxes):
        y = min(float(point[1]) for point in box) / height
        lines.append(OCRLine(str(text).strip(), float(score), y))
    return OCRPage(tuple(lines))


def read_document(data: bytes, kind: str) -> list[OCRPage]:
    """Lee un PDF escaneado o una imagen sin escribir copias en disco."""
    if kind == "pdf":
        import pymupdf

        try:
            document = pymupdf.open(stream=data, filetype="pdf")
            if document.needs_pass or not 1 <= len(document) <= MAX_PAGES:
                raise DocumentReadError("El PDF está protegido o tiene demasiadas páginas.")
            pages = []
            for page in document:
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                pages.append(_read_image(pixmap.tobytes("png"), max_edge=1800))
            document.close()
            return pages
        except (pymupdf.FileDataError, pymupdf.EmptyFileError) as exc:
            raise DocumentReadError("No se pudo leer el PDF.") from exc
    return [_read_image(data)]


def _match_digits(text: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(text)
    return re.sub(r"\D", "", match.group(0)) if match else None


def _looks_like_name(value: str) -> bool:
    value = value.strip(" _.,:")
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", value)
    if not 2 <= len(words) <= 6 or len(value) > 80:
        return False
    forbidden = {
        "nombre", "cedula", "cliente", "identidad", "envio", "autorizo",
        "paquete", "liberacion", "domicilio", "facturacion", "direccion",
        "exoneracion", "comercial", "consignado", "apellido", "firma",
        "celular", "pasaporte", "igual", "num",
    }
    return not any(_norm(word) in forbidden for word in words)


def _after_label(lines: list[str], label: str, *, before: bool = False,
                 name: bool = False) -> str | None:
    for index, line in enumerate(lines):
        match = re.search(label, _norm(line), re.IGNORECASE)
        if not match:
            continue
        candidates = []
        if before and index:
            candidates.append(lines[index - 1])
        # La etiqueta y el valor pueden compartir una línea.
        suffix = line[match.end():].strip(" :_-,.")
        if suffix:
            candidates.append(suffix)
        candidates.extend(lines[index + 1:index + 3])
        for candidate in candidates:
            candidate = candidate.strip(" _.,:")
            if not candidate:
                continue
            if name and _looks_like_name(candidate):
                return candidate
            if not name and not re.match(
                r"^(?:nombre|cedula|n[uú]mero|firma|direcci[oó]n|exoneraci[oó]n)\b",
                _norm(candidate), re.IGNORECASE,
            ):
                return candidate
    return None


def _tracking(lines: list[str]) -> str | None:
    for line in lines:
        if "ejemplo" in _norm(line):
            continue
        match = TRACKING_RE.search(line)
        if match and "000000000" not in match.group(0):
            return re.sub(r"\s+", "", match.group(0)).upper()
    return None


def _signature_near_label(page: OCRPage) -> bool:
    for index, line in enumerate(page.lines):
        if line.y < .78 or "firma" not in _norm(line.text) or "cedula" not in _norm(line.text):
            continue
        for candidate in page.lines[index + 1:index + 4]:
            cleaned = candidate.text.strip(" _.:-")
            if (candidate.y < .92 and candidate.y - line.y < .08
                    and 2 <= len(cleaned) <= 30 and re.search(r"[A-Za-z]", cleaned)
                    and "celular" not in _norm(cleaned)
                    and "numero" not in _norm(cleaned)
                    and "correos" not in _norm(cleaned)):
                return True
    return False


def _exemption_selection(lines: list[str]) -> str | None:
    start = next((i for i, line in enumerate(lines) if "deseas aplicar" in _norm(line)), None)
    if start is None:
        return None
    options = [_norm(line).strip() for line in lines[start + 1:start + 8]]
    yes = next((i for i, item in enumerate(options) if item == "si"), None)
    no = next((i for i, item in enumerate(options) if item == "no"), None)
    mark = next((i for i, item in enumerate(options) if item in {"x", "✓", "v"}), None)
    if yes is None or no is None or mark is None:
        return None
    return "si" if mark < no else "no"


def extract_form(pages: list[OCRPage]) -> dict:
    first = pages[0].texts if pages else []
    second = pages[1].texts if len(pages) > 1 else []
    top_id = None
    for line in first[:20]:
        if "cedula" in _norm(line):
            top_id = _match_digits(line, ID_RE)
            if top_id:
                break
    bottom_id_text = _after_label(first, r"cedula de identidad")
    phone_text = _after_label(first, r"celular")
    client_name = _after_label(first, r"nombre del cliente", before=True, name=True)
    authorizer = _after_label(first[:20], r"\byo\b", name=True)
    consignee = _after_label(second, r"consignado a nombre", name=True)
    description = _after_label(second, r"es la siguiente")
    if description and ("firma" in _norm(description) or len(description) < 8):
        description = None
    signature_second = any(
        .81 < line.y < .92 and 2 <= len(line.text.strip(" _.:-")) <= 30
        and re.search(r"[A-Za-z]", line.text)
        and "firma" not in _norm(line.text)
        and "correos" not in _norm(line.text)
        for line in (pages[1].lines if len(pages) > 1 else ())
    )
    return {
        "paginas": len(pages),
        "nombre_autorizacion": authorizer,
        "cedula_autorizacion": top_id,
        "envio_autorizacion": _tracking(first),
        "nombre_cliente": client_name,
        "cedula_cliente": _match_digits(bottom_id_text or "", ID_RE),
        "celular": _match_digits(phone_text or "", PHONE_RE),
        "firma_autorizacion": _signature_near_label(pages[0]) if pages else False,
        "exoneracion": _exemption_selection(second),
        "envio_exoneracion": _tracking(second),
        "consignado_a": consignee,
        "mercancia": description,
        "firma_exoneracion": signature_second,
    }


def extract_id_front(page: OCRPage) -> dict:
    lines = page.texts
    given = _after_label(lines, r"\bnombre\b", name=True)
    last1 = _after_label(lines, r"1.?\s*apellido")
    last2 = _after_label(lines, r"2.?\s*apellido")
    name = " ".join(part for part in (given, last1, last2) if part) if given and last1 and last2 else None
    card_id = next((_match_digits(line, ID_RE) for line in lines[:20] if _match_digits(line, ID_RE)), None)
    return {"nombre": name, "cedula": card_id}


def extract_id_back(page: OCRPage) -> dict:
    lines = page.texts
    card_line = next((line for line in lines if "numero de cedula" in _norm(line)), "")
    expiry_line = next((line for line in lines if "vencimiento" in _norm(line)), "")
    return {
        "cedula": _match_digits(card_line, ID_RE),
        "vencimiento": _match_digits(expiry_line, re.compile(r"(?<!\d)(?:\d[\s/-]*){8}(?!\d)")),
    }


def _invoice_name(lines: list[str], label: str) -> str | None:
    value = _after_label(lines, label)
    if not value:
        return None
    value = re.split(r"\+?506\s*\d", value, maxsplit=1)[0].strip(" ,")
    return value if _looks_like_name(value) else None


def extract_invoice(pages: list[OCRPage]) -> dict:
    lines = [text for page in pages for text in page.texts]
    name_billing = _invoice_name(lines, r"direccion de facturacion")
    name_shipping = _invoice_name(lines, r"direccion de envio")
    total_text = _after_label(lines, r"total del pedido")
    total = _match_digits(total_text or "", re.compile(r"(?<!\d)\d[\d,.\s]*(?!\d)"))
    item = None
    for index, line in enumerate(lines):
        if re.search(r"(?:detalle|productos|articulos del pedido|descripcion de articulos)", _norm(line)):
            for candidate in lines[index + 1:index + 8]:
                if re.search(r"\btotal\b|\benvio\b|metodo de pago", _norm(candidate)):
                    break
                if len(candidate.strip()) >= 8 and re.search(r"[A-Za-z]", candidate):
                    item = candidate.strip()
                    break
            if item:
                break
    return {
        "nombre_facturacion": name_billing,
        "nombre_envio": name_shipping,
        "total": total,
        "mercancia": item,
    }


def extract_bundle(files: dict[str, tuple[bytes, str]]) -> dict:
    """Devuelve campos privados usados solo por el validador de la petición."""
    pages = {role: read_document(data, kind) for role, (data, kind) in files.items()}
    for role, value in pages.items():
        if not value or not any(page.lines for page in value):
            raise DocumentReadError(f"No se pudo leer el contenido de {role}.")
    return {
        "formulario": extract_form(pages["formulario"]),
        "cedula_frente": extract_id_front(pages["cedula_frente"][0]),
        "cedula_reverso": extract_id_back(pages["cedula_reverso"][0]),
        "factura": extract_invoice(pages["factura"]),
    }
