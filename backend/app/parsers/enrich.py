"""Enriquecimiento de operaciones: método de pago, contraparte, referencias.

Todo se deriva de la descripción reconstruida del movimiento. Las reglas están
ordenadas de lo más específico a lo más genérico.
"""

from __future__ import annotations

import re
import unicodedata

_TRANSLITERATION = str.maketrans(
    {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
        "Á": "A",
        "É": "E",
        "Í": "I",
        "Ó": "O",
        "Ú": "U",
        "Ñ": "N",
    }
)

_METHOD_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"COMISION PAGO MOVIL INTERBANCARIO"), "comision_pago_movil"),
    (re.compile(r"COMISION PAGO MOVIL"), "comision_pago_movil"),
    (re.compile(r"COMISION POR SOLICITUD DE ENVIO DE CREDITO"), "comision_credito_inmediato"),
    (re.compile(r"COMISION DATO ERRADO"), "comision"),
    (re.compile(r"COMISION"), "comision"),
    (re.compile(r"PAGO MOVIL A UN MOVIL"), "pago_movil"),
    (re.compile(r"PAGO MOVIL COMERCIAL INTERBANCARIO"), "pago_movil"),
    (re.compile(r"PAGO MOVIL INTERBANCARIO"), "pago_movil"),
    (re.compile(r"RECEPCION DE PAGO MOVIL"), "pago_movil"),
    (re.compile(r"PAGO MOVIL"), "pago_movil"),
    (re.compile(r"OPERACION DE CREDITO INMEDIATO"), "credito_inmediato"),
    (re.compile(r"TRANSFERENCIA RECIBIDA"), "transferencia_recibida"),
    (re.compile(r"TRANSFERENCIA DESDE LA CUENTA"), "transferencia_enviada"),
    (re.compile(r"CONSUMO PUNTO DE VENTA"), "punto_de_venta"),
    (re.compile(r"CONSUMO TARJETA"), "tarjeta_debito"),
    (re.compile(r"PAGO A TERCEROS VIA INTERNET"), "pago_terceros"),
    (re.compile(r"PAGO A (DIGITEL|MOVISTAR|INTER)"), "pago_servicios"),
    (re.compile(r"CANCELAC\.?FACTURA"), "pago_servicios"),
    (re.compile(r"TARIFA MANTENIMIENTO"), "mantenimiento"),
    (re.compile(r"EMISION EDO\.? DE CTA"), "emision_estado"),
    (re.compile(r"IMPUESTO|IGTF"), "impuesto"),
    (re.compile(r"CHEQUE"), "cheque"),
]

_RE_COUNTERPART = re.compile(
    r"(?:CUENTA DE|ENTA DE)\s+([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9 .,&'\-]{1,60}?)\s*\*\*\*(\d+)"
)
_RE_COUNTERPART_ALT = re.compile(r"\*\*\*(\d+)\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ .,'\-]{2,50}?)(?:\s+POR|\s+EL|$)")
_RE_RECEIVED_FROM = re.compile(r"RECIBIDA DESDE LA CUENTA\s+\*\*\*(\d+)")
_RE_DEST_ACCOUNT = re.compile(r"(?:A LA CUENTA|CUENTA)\s+(\d{10,20})")
_RE_REFERENCE = re.compile(r"(?:CON REFERENCIA|REFERENCIA|NUMERO ID\.?)\s*:?\s*(\d{5,})")
_RE_AN = re.compile(r"A/N DE\s+([A-Z0-9]+)")
_RE_CONCEPT = re.compile(
    r"POR CONCEPTO DE:?\s*(.{0,80}?)(?:\s?EL \d{2}-\d{2}-\d{2}|\s+REALIZADA|\s*$)"
)
_RE_OCCURRED = re.compile(r"EL\s+(\d{2}-\d{2}-\d{2})\s+A LAS\s+(\d{2}:\d{2}:\d{2})\s+HORAS")
_RE_PHONE = re.compile(r"\b0(4\d{2})[-\s]?(\d{7})\b")
_RE_BANK = re.compile(
    r"EN\s+((?:BANCO|BANESCO|BBVA|BNC|BANCAMIGA|BANPLUS|BANCO DEL|BANCO DE)[A-ZÁÉÍÓÚÑ .,&'\-]{2,60}?)(?:,|\s+S\.?A|\s+B\b|\s+BA\b|$)"
)


def normalize_text(text: str) -> str:
    """Clave de búsqueda robusta a los cortes de palabra del PDF.

    Elimina acentos, espacios y puntuación, de modo que una consulta como
    ``cuenta`` encuentre tanto ``CUENTA`` como ``CU ENTA`` o ``CU\nENTA``.
    """
    text = text.translate(_TRANSLITERATION)
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_text.lower())


def classify_method(description: str) -> str:
    upper = description.upper()
    for pattern, method in _METHOD_RULES:
        if pattern.search(upper):
            return method
    return "otro"


def _clean_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name).strip(" .,-")
    return cleaned.title() if cleaned.isupper() else cleaned


def enrich_operation(description: str) -> dict[str, str | None]:
    """Extrae campos estructurados de una descripción reconstruida."""
    result: dict[str, str | None] = {
        "method": classify_method(description),
        "counterpart": None,
        "counterpart_account": None,
        "counterpart_bank": None,
        "reference": None,
        "concept": None,
        "occurred_at": None,
        "phone": None,
    }

    match = _RE_COUNTERPART.search(description)
    if match:
        result["counterpart"] = _clean_name(match.group(1))
        result["counterpart_account"] = match.group(2)
    else:
        match = _RE_COUNTERPART_ALT.search(description)
        if match and result["counterpart"] is None:
            result["counterpart_account"] = match.group(1)
            result["counterpart"] = _clean_name(match.group(2))

    match = _RE_RECEIVED_FROM.search(description)
    if match and result["counterpart_account"] is None:
        result["counterpart_account"] = match.group(1)

    match = _RE_DEST_ACCOUNT.search(description)
    if match and result["counterpart_account"] is None:
        result["counterpart_account"] = match.group(1)

    match = _RE_REFERENCE.search(description)
    if match:
        result["reference"] = match.group(1)
    else:
        match = _RE_AN.search(description)
        if match:
            result["reference"] = match.group(1)

    match = _RE_CONCEPT.search(description)
    if match:
        concept = re.sub(r"\s+", " ", match.group(1)).strip(" .,-")
        result["concept"] = concept or None

    match = _RE_OCCURRED.search(description)
    if match:
        result["occurred_at"] = f"{match.group(1)} {match.group(2)}"

    match = _RE_PHONE.search(description)
    if match:
        result["phone"] = f"{match.group(1)}-{match.group(2)}"

    match = _RE_BANK.search(description.upper())
    if match:
        result["counterpart_bank"] = _clean_name(match.group(1))

    return result
