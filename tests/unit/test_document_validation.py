"""Reglas del piloto con datos ficticios, sin guardar documentos reales."""

from copy import deepcopy

from support_agent.document_validation import validar_expediente
from support_agent.document_ocr import OCRLine, OCRPage, extract_form


def expediente() -> dict:
    return {
        "formulario": {
            "paginas": 2,
            "nombre_autorizacion": "Ana María Solís Vega",
            "cedula_autorizacion": "123456789",
            "envio_autorizacion": "RP123456789MU",
            "nombre_cliente": "Ana Maria Solis Vega",
            "cedula_cliente": "1 2345 6789",
            "celular": "88889999",
            "firma_autorizacion": True,
            "exoneracion": "si",
            "envio_exoneracion": "RP123456789MU",
            "consignado_a": "Ana María Solís Vega",
            "mercancia": "Zapatos deportivos",
            "firma_exoneracion": True,
        },
        "cedula_frente": {"nombre": "Ana María Solís Vega", "cedula": "123456789"},
        "cedula_reverso": {"cedula": "1 2345 6789", "vencimiento": "31122099"},
        "factura": {
            "nombre_facturacion": "Ana María Solís Vega",
            "nombre_envio": "Ana María Solís Vega",
            "total": "8148",
            "mercancia": "Zapatos deportivos",
        },
    }


def hallazgo(report: dict, code: str) -> str:
    return next(item["estado"] for item in report["verificaciones"] if item["codigo"] == code)


def test_expediente_completo_y_coincidente():
    report = validar_expediente(expediente())
    assert report["resultado"] == "cumple"
    assert report["referir_agente"] is False


def test_nombre_completo_distinto_es_diferente():
    data = expediente()
    data["formulario"]["nombre_autorizacion"] = "Ana Solís Vega"
    report = validar_expediente(data)
    assert hallazgo(report, "nombre_formulario_cedula") == "diferente"
    assert report["resultado"] == "no_cumple"


def test_factura_a_nombre_de_otro_no_cumple():
    data = expediente()
    data["factura"]["nombre_facturacion"] = "Luis Pérez Castro"
    report = validar_expediente(data)
    assert hallazgo(report, "nombre_factura") == "diferente"
    assert report["resultado"] == "no_cumple"


def test_campo_vacio_es_faltante():
    data = expediente()
    data["formulario"]["celular"] = ""
    report = validar_expediente(data)
    assert hallazgo(report, "campo_celular_formulario") == "faltante"
    assert report["resultado"] == "no_cumple"
    assert report["referir_agente"] is True


def test_factura_sin_detalle_remite_a_agente():
    data = expediente()
    data["factura"]["mercancia"] = None
    report = validar_expediente(data)
    assert hallazgo(report, "mercancia_factura") == "no_verificable"
    assert report["resultado"] == "requiere_agente"
    assert report["referir_agente"] is True


def test_segunda_pagina_sin_campos_tampoco_esta_completa():
    data = expediente()
    data["formulario"]["exoneracion"] = "no"
    data["formulario"]["mercancia"] = ""
    report = validar_expediente(data)
    assert hallazgo(report, "campo_mercancia_formulario") == "faltante"
    assert report["resultado"] == "no_cumple"


def test_informe_no_incluye_valores_personales():
    data = deepcopy(expediente())
    data["factura"]["nombre_facturacion"] = "Luis Pérez Castro"
    text = str(validar_expediente(data))
    for private in ("Ana María Solís Vega", "Luis Pérez Castro", "123456789", "88889999"):
        assert private not in text


def test_etiquetas_y_pie_de_pagina_no_cuentan_como_campos_llenos():
    first = OCRPage(tuple(OCRLine(text, .99, y) for text, y in (
        ("Nombre del cliente:", .83),
        ("Cédula de identidad/pasaporte:", .84),
        ("Núm. Celular", .84),
        ("Firma (igual a la cédula):", .86),
        ("correos.go.cr", .95),
    )))
    second = OCRPage(tuple(OCRLine(text, .99, y) for text, y in (
        ("(Firma igual que en la identificación)", .8),
        ("correos.go.cr", .95),
    )))
    form = extract_form([first, second])
    assert form["nombre_cliente"] is None
    assert form["firma_autorizacion"] is False
    assert form["firma_exoneracion"] is False
