"""Enriquecimiento de operaciones: método de pago, contraparte, referencias.

Todo se deriva de la descripción reconstruida del movimiento. Las reglas están
ordenadas de lo más específico a lo más genérico y cubren los distintos formatos
que Mercantil ha usado entre 2023 y 2026.
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
    (re.compile(r"RECEPCION DE PAGO"), "pago_movil"),
    (re.compile(r"PAGO MOVIL"), "pago_movil"),
    (re.compile(r"OPERACION DE CREDITO INMEDIATO"), "credito_inmediato"),
    (re.compile(r"TRANSFERENCIA RECIBIDA"), "transferencia_recibida"),
    (re.compile(r"TRANSFERENCIA DESDE LA CUENTA"), "transferencia_enviada"),
    (re.compile(r"PAGO POR INTERNET DE MISMOBANCO"), "pago_terceros"),
    (re.compile(r"PAGO POR INTERNET"), "pago_terceros"),
    (re.compile(r"TRANSFERENCIA POR INTERNET|TRANFERENCIA"), "transferencia"),
    (re.compile(r"PAGO AUTORIZADO A LA EMPRESA"), "pago_servicios"),
    (re.compile(r"PAGO DE SERVICIO"), "pago_servicios"),
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
_RE_COUNTERPART_ALT = re.compile(
    r"\*\*\*(\d+)\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ .,'\-]{2,50}?)(?:\s+POR|\s+EL|$)"
)
_RE_RECEIVED_FROM = re.compile(r"RECIBIDA DESDE LA CUENTA\s+\*\*\*(\d+)")
_RE_ORDENADA = re.compile(
    r"ORDENADA POR\s+(?:[VEJ]?\d{5,10})\s+"
    r"([A-Za-zÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑ .,'\-]{2,60}?)\s+"
    r"(?:A LA CUENTA|CUENTA)\s+(\d{10,20})"
)
_RE_ORDENADA_SIN_NOMBRE = re.compile(
    r"ORDENADA POR\s+[VEJ]?\d{5,10}\s+(?:A LA CUENTA|CUENTA)\s+(\d{10,20})"
)
_RE_AN_NAME = re.compile(
    r"A/N DE\s+[A-Z0-9]+\s+([A-Za-zÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑ .,'\-]{2,60}?)\s+"
    r"(?:A LA CUENTA|CUENTA)\s+(\d{10,20})"
)
_RE_ENVIADO_POR = re.compile(
    r"ENVIADO POR\s+([A-Za-zÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑ .,'\-]{2,60}?)\s+DESDE EL"
)
_RE_2023_A = re.compile(r"\bA\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ .,'\-]{3,60}?)\s+POR LA CANTIDAD")
_RE_2023_CTA = re.compile(r"DESDE LA CUENTA NUMERO\s+(\d{8,20})\s+A LA CUENTA NUMERO\s+(\d{8,20})")
_RE_DEST_ACCOUNT = re.compile(r"(?:A LA CUENTA|CUENTA)\s+(\d{10,20})")
_RE_CLIENT_ID = re.compile(r"IDENTIFICACION DEL CLIENTE\s*EN LA EMPRESA ES\s+([VEJ]?\d{5,10})")
_RE_REFERENCE = re.compile(
    r"(?:CON REFERENCIA|REFERENCIA|NUMERO ID\.?|FACTURA NUMERO)\s*:?\s*(\d{5,})"
)
_RE_AN = re.compile(r"A/N DE\s+([A-Z0-9]+)")
_RE_CONCEPT = re.compile(
    r"POR(?:\s*EL)?\s*CONCEPTO\s*DE:?\s*(.{0,80}?)(?:\s?P?EL \d{2}-\d{2}-\d{2}|\s+REALIZADA|\s*$)"
)
_RE_OCCURRED = re.compile(r"EL\s+(\d{2}-\d{2}-\d{2})\s+A LAS\s+(\d{2}:\d{2}:\d{2})\s+HORAS")
_RE_PHONE = re.compile(r"\b0(4\d{2})[-\s]?(\d{7})\b")

_BANK_START = r"(?:BANCO|BANESCO|BBVA|BNC|BANCAMIGA|BANPLUS|MERCANTIL)"
_RE_BANK = re.compile(rf"(?:EN|DE)\s+({_BANK_START}[A-ZÁÉÍÓÚÑ0-9 .,'&-]{{2,70}})")
_BANK_STOP = re.compile(r"\s+(?:POR|CON|EL|A/N|A LA|BAJO|DESDE|PARA)\s+.*$", re.IGNORECASE)
_PLACEHOLDER_NAMES = re.compile(r"^(?:N/?A|NOMBRE-BENEFICIARIO(?:-TPG)?|BENEFICIARIO)$", re.IGNORECASE)


def normalize_text(text: str) -> str:
    """Clave de búsqueda robusta a los cortes de palabra del PDF.

    Elimina acentos, espacios y puntuación, de modo que una consulta como
    ``cuenta`` encuentre tanto ``CUENTA`` como ``CU ENTA`` o ``CU\\nENTA``.
    """
    text = text.translate(_TRANSLITERATION)
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_text.lower())


def classify_method(description: str, direction: str | None = None) -> str:
    upper = description.upper()
    for pattern, method in _METHOD_RULES:
        if pattern.search(upper):
            if method == "transferencia":
                return "transferencia_recibida" if direction == "abono" else "transferencia_enviada"
            return method
    return "otro"


def _clean_name(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = re.sub(r"\s+", " ", name).strip(" .,-")
    if not cleaned or _PLACEHOLDER_NAMES.match(cleaned):
        return None
    return cleaned.title() if cleaned.isupper() else cleaned


def _clean_bank(raw: str) -> str | None:
    text = _BANK_STOP.sub("", raw)
    text = text.split(",")[0]
    # Sufijos societarios y letras sueltas al final: S.A., S.A.C.A., C.A., B, BA, S
    for _ in range(3):
        before = text
        text = re.sub(r"\s+S\.?\s*A\.?(?:\s*C\.?\s*A\.?)?\s*$", "", text)
        text = re.sub(r"\s+C\.?\s*A\.?\s*$", "", text)
        text = re.sub(r"\s+B(?:A)?\s*$", "", text)
        text = re.sub(r"\s+S\s*$", "", text)
        if text == before:
            break
    text = re.sub(r"\s+", " ", text).strip(" .,-")
    if len(text) < 5:
        return None
    return text.title() if text.isupper() else text


def enrich_operation(description: str, direction: str | None = None) -> dict[str, str | None]:
    """Extrae campos estructurados de una descripción reconstruida."""
    result: dict[str, str | None] = {
        "method": classify_method(description, direction),
        "counterpart": None,
        "counterpart_account": None,
        "counterpart_bank": None,
        "reference": None,
        "concept": None,
        "occurred_at": None,
        "phone": None,
    }

    # --- contraparte y cuenta ---
    match = _RE_COUNTERPART.search(description)
    if match:
        result["counterpart"] = _clean_name(match.group(1))
        result["counterpart_account"] = match.group(2)
    if result["counterpart"] is None:
        match = _RE_ORDENADA.search(description)
        if match:
            result["counterpart"] = _clean_name(match.group(1))
            result["counterpart_account"] = match.group(2)
    if result["counterpart"] is None:
        match = _RE_AN_NAME.search(description)
        if match:
            result["counterpart"] = _clean_name(match.group(1))
            result["counterpart_account"] = match.group(2)
    if result["counterpart"] is None:
        match = _RE_ENVIADO_POR.search(description)
        if match:
            result["counterpart"] = _clean_name(match.group(1))
    if result["counterpart"] is None:
        match = _RE_2023_A.search(description)
        if match:
            result["counterpart"] = _clean_name(match.group(1))
    if result["counterpart"] is None:
        match = _RE_CLIENT_ID.search(description)
        if match:
            result["counterpart"] = match.group(1)
    if result["counterpart"] is None:
        match = _RE_COUNTERPART_ALT.search(description)
        if match:
            result["counterpart_account"] = match.group(1)
            result["counterpart"] = _clean_name(match.group(2))

    if result["counterpart_account"] is None:
        match = _RE_RECEIVED_FROM.search(description)
        if match:
            result["counterpart_account"] = match.group(1)
    if result["counterpart_account"] is None:
        match = _RE_ORDENADA_SIN_NOMBRE.search(description)
        if match:
            result["counterpart_account"] = match.group(1)
    if result["counterpart_account"] is None:
        match = _RE_2023_CTA.search(description)
        if match:
            result["counterpart_account"] = (
                match.group(1) if direction == "abono" else match.group(2)
            )
    if result["counterpart_account"] is None:
        match = _RE_DEST_ACCOUNT.search(description)
        if match:
            result["counterpart_account"] = match.group(1)

    # --- banco contraparte ---
    match = _RE_BANK.search(description)
    if match:
        result["counterpart_bank"] = _clean_bank(match.group(1))

    # --- referencia ---
    match = _RE_REFERENCE.search(description)
    if match:
        result["reference"] = match.group(1)
    else:
        match = _RE_AN.search(description)
        if match:
            result["reference"] = match.group(1)

    # --- concepto ---
    match = _RE_CONCEPT.search(description)
    if match:
        concept = re.sub(r"\s+", " ", match.group(1)).strip(" .,-")
        if concept.upper() not in ("", "N/A", "P"):
            result["concept"] = concept

    # --- fecha/hora de la operación, teléfono ---
    match = _RE_OCCURRED.search(description)
    if match:
        result["occurred_at"] = f"{match.group(1)} {match.group(2)}"

    match = _RE_PHONE.search(description)
    if match:
        result["phone"] = f"{match.group(1)}-{match.group(2)}"

    return result
