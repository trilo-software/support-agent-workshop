"""Reglas deterministas del piloto de autorización aduanera.

Los valores extraídos se usan solo durante la petición. El informe público
contiene estados y referencias, nunca nombres, cédulas ni texto OCR completo.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime


def _normalizar_nombre(value: str | None) -> str:
    if not value:
        return ""
    value = "".join(
        char for char in unicodedata.normalize("NFD", value.upper())
        if unicodedata.category(char) != "Mn"
    )
    return " ".join(re.findall(r"[A-Z]+", value))


def _normalizar_numero(value: str | None) -> str:
    return "".join(re.findall(r"\d", value or ""))


def _normalizar_texto(value: str | None) -> str:
    return _normalizar_nombre(value)


def validar_expediente(datos: dict) -> dict:
    """Valida campos y coincidencias sin delegar decisiones a un LLM."""
    if datos.get("_ocr_error"):
        return {
            "resultado": "requiere_agente",
            "referir_agente": True,
            "verificaciones": [{
                "codigo": "lectura_documento", "campo": "Lectura del expediente",
                "estado": "no_verificable", "detalle": datos["_ocr_error"],
                "fuente": "adjuntos",
            }],
        }
    form = datos.get("formulario") or {}
    front = datos.get("cedula_frente") or {}
    back = datos.get("cedula_reverso") or {}
    invoice = datos.get("factura") or {}
    checks: list[dict] = []

    def add(code: str, label: str, status: str, detail: str, source: str) -> None:
        checks.append({
            "codigo": code, "campo": label, "estado": status,
            "detalle": detail, "fuente": source,
        })

    def required(key: str, label: str, data: dict, source: str) -> bool:
        value = data.get(key)
        present = bool(value and (not isinstance(value, str) or value.strip()))
        add(
            f"campo_{key}_{source}", label,
            "coincide" if present else "faltante",
            "Campo presente." if present else "El campo obligatorio está vacío o no se pudo leer.",
            source,
        )
        return present

    if form.get("paginas", 0) < 2:
        add("paginas_formulario", "Páginas del formulario", "faltante",
            "Se necesitan las dos páginas del formulario.", "formulario")
    else:
        add("paginas_formulario", "Páginas del formulario", "coincide",
            "Se recibieron las dos páginas.", "formulario")

    for key, label in (
        ("nombre_autorizacion", "Nombre de quien autoriza"),
        ("cedula_autorizacion", "Cédula de quien autoriza"),
        ("envio_autorizacion", "Número de envío en autorización"),
        ("nombre_cliente", "Nombre del cliente"),
        ("cedula_cliente", "Cédula del cliente"),
        ("celular", "Número celular"),
        ("firma_autorizacion", "Firma de autorización"),
        ("exoneracion", "Selección de exoneración"),
    ):
        required(key, label, form, "formulario")

    for key, label in (
        ("envio_exoneracion", "Número de envío en exoneración"),
        ("consignado_a", "Nombre del destinatario"),
        ("mercancia", "Descripción de la mercancía"),
        ("firma_exoneracion", "Firma de exoneración"),
    ):
        required(key, label, form, "formulario")

    for role, entries in (
        ("cedula_frente", (("nombre", "Nombre en cédula"), ("cedula", "Número en frente de cédula"))),
        ("cedula_reverso", (("cedula", "Número en reverso de cédula"), ("vencimiento", "Vencimiento de cédula"))),
        ("factura", (("nombre_facturacion", "Nombre en factura"), ("total", "Valor de compra"))),
    ):
        for key, label in entries:
            required(key, label, datos.get(role) or {}, role)

    def compare(code: str, label: str, a: str | None, b: str | None,
                source: str, normalizer) -> None:
        if not a or not b:
            return  # Los campos ausentes ya quedaron como faltantes.
        match = normalizer(a) == normalizer(b)
        add(code, label, "coincide" if match else "diferente",
            "Los datos coinciden." if match else "Los datos no coinciden.", source)

    compare("nombre_formulario_cedula", "Nombre del formulario y cédula",
            form.get("nombre_autorizacion"), front.get("nombre"),
            "formulario ↔ cédula frente", _normalizar_nombre)
    compare("nombre_interno", "Nombre en ambas secciones del formulario",
            form.get("nombre_autorizacion"), form.get("nombre_cliente"),
            "formulario", _normalizar_nombre)
    compare("cedula_formulario_cedula", "Cédula del formulario y frente",
            form.get("cedula_autorizacion"), front.get("cedula"),
            "formulario ↔ cédula frente", _normalizar_numero)
    compare("cedula_frente_reverso", "Número en ambas caras de la cédula",
            front.get("cedula"), back.get("cedula"),
            "cédula frente ↔ reverso", _normalizar_numero)
    compare("cedula_interna", "Cédula en ambas secciones del formulario",
            form.get("cedula_autorizacion"), form.get("cedula_cliente"),
            "formulario", _normalizar_numero)
    compare("envio_interno", "Número de envío en ambas páginas",
            form.get("envio_autorizacion"), form.get("envio_exoneracion"),
            "formulario", lambda x: re.sub(r"\s+", "", x.upper()))
    compare("consignatario", "Destinatario y solicitante",
            form.get("nombre_autorizacion"), form.get("consignado_a"),
            "formulario", _normalizar_nombre)
    compare("nombre_factura", "Nombre de factura y solicitante",
            invoice.get("nombre_facturacion"), form.get("nombre_autorizacion"),
            "factura ↔ formulario", _normalizar_nombre)
    if invoice.get("nombre_envio"):
        compare("nombre_envio_factura", "Nombre de envío en factura y solicitante",
                invoice.get("nombre_envio"), form.get("nombre_autorizacion"),
                "factura ↔ formulario", _normalizar_nombre)

    if back.get("vencimiento"):
        try:
            expiry = datetime.strptime(back["vencimiento"], "%d%m%Y").date()
        except ValueError:
            add("vigencia_cedula", "Vigencia de cédula", "no_verificable",
                "No se pudo interpretar la fecha de vencimiento.", "cédula reverso")
        else:
            valid = expiry >= date.today()
            add("vigencia_cedula", "Vigencia de cédula",
                "coincide" if valid else "diferente",
                "La fecha visible está vigente." if valid else "La fecha visible indica una cédula vencida.",
                "cédula reverso")

    # Una cifra en "total de artículos" no prueba qué producto se compró.
    # Solo se acepta una descripción explícita de la factura.
    item = invoice.get("mercancia")
    declared = form.get("mercancia")
    if declared:
        if not item:
            add("mercancia_factura", "Mercancía declarada y factura", "no_verificable",
                "La factura no muestra el detalle de los artículos; debe revisarlo un agente.",
                "formulario ↔ factura")
        elif _normalizar_texto(item) == _normalizar_texto(declared):
            add("mercancia_factura", "Mercancía declarada y factura", "coincide",
                "La descripción coincide literalmente.", "formulario ↔ factura")
        else:
            add("mercancia_factura", "Mercancía declarada y factura", "no_verificable",
                "Las descripciones no son iguales; un agente debe comprobar si son equivalentes.",
                "formulario ↔ factura")

    has_failure = any(c["estado"] in {"faltante", "diferente"} for c in checks)
    # OCR no permite distinguir con certeza un campo realmente vacío de uno
    # ilegible; el estado sigue siendo FALTANTE, pero se remite para revisión.
    needs_agent = any(c["estado"] in {"faltante", "no_verificable"} for c in checks)
    result = "no_cumple" if has_failure else "requiere_agente" if needs_agent else "cumple"
    return {
        "resultado": result,
        "referir_agente": needs_agent,
        "verificaciones": checks,
    }


def formatear_informe(report: dict) -> str:
    header = {
        "cumple": "El expediente cumple las comprobaciones automáticas.",
        "no_cumple": "El expediente no cumple las comprobaciones automáticas.",
        "requiere_agente": "El expediente requiere revisión de un agente.",
    }[report["resultado"]]
    lines = [header]
    for check in report["verificaciones"]:
        if check["estado"] != "coincide":
            lines.append(f"• {check['campo']}: {check['estado'].replace('_', ' ').upper()}. {check['detalle']}")
    if report["referir_agente"]:
        ticket = report.get("ticket_id")
        suffix = f" (ticket #{ticket})" if ticket is not None else ""
        lines.append(f"Los campos faltantes o no verificables se remiten a un agente para revisión{suffix}.")
    return "\n".join(lines)
