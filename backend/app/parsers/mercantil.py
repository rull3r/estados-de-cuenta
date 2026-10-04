"""Adapter de Mercantil - Estado de Cuenta Corriente.

Estructura del PDF (validada sobre 44 estados de cuenta 2023-2026):

- Página 0: resumen oficial (saldos y totales del período).
- Sección ``MOVIMIENTOS DE CUENTA``: libro principal a dos columnas por página.
  Columnas: FECHA, NUMERO, DESCRIPCION, CARGOS, ABONOS, SALDO, IMPUESTO.
  Los montos van alineados a la derecha y el ancho de columnas varía entre años,
  por eso las anclas se recalculan en cada página leyendo el encabezado.
- Anexo ``MERCANTIL EN LINEA``: operaciones con la llave Mercantil
  (FECHA TR., FECHA OPERACION, descripción, MONTO). Es un subconjunto del libro.
- Sección ``PUNTOS DE VENTA``: consumo con tarjeta (también subconjunto del libro).
- Las descripciones se cortan a mitad de palabra; se reconstruyen uniendo por
  borde de columna.
- El banco imprime saldos intermedios esporádicos (p. ej. en filas de consumo)
  que se usan para localizar filas omitidas.
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz

from . import enrich
from .base import file_hash
from .linegrid import (
    DATE_RE,
    DOTTED_DATE_RE,
    Line,
    classify_amount,
    find_column_anchors,
    is_amount,
    page_lines,
    page_lines_raw,
    parse_amount,
)
from .model import (
    AnnexOperation,
    Checkpoint,
    CoverSummary,
    Operation,
    ParseResult,
    PosOperation,
)

_TIMESTAMP_RE = re.compile(r"EL\s+(\d{2}-\d{2}-\d{2})\s+A LAS\s+(\d{2}:\d{2}:\d{2})")
_ACCOUNT_RE = re.compile(r"^\d{9,11}$")
_AMOUNT_ROW_LABELS = {
    "saldo_inicio": ("SALDO", "INICIO"),
    "depositos": ("DEPOSITOS",),
    "otros_creditos": ("CREDITOS",),
    "cheques": ("CHEQUES",),
    "otros_debitos": ("DEBITOS",),
    "igtf": ("IGTF",),
    "saldo_final": ("SALDO", "FINAL"),
}


_REPAIRS: list[tuple[re.Pattern[str], str]] = [
    # Cortes duros que pegaron el timestamp al texto anterior: "...DE P" + "EL 02-01-26"
    (re.compile(r"(?<=[A-Za-z0-9/])(P?EL \d{2}-\d{2}-\d{2} A LAS)"), r" \1"),
    # Timestamp con año completo pegado a la palabra anterior: "...PERSONASEL 01/09/2024 A LAS"
    (re.compile(r"(?<=[A-Za-zÁÉÍÓÚÑ])(EL \d{2}/\d{2}/\d{4} A LAS)"), r" \1"),
    # "A LAS15:07" -> "A LAS 15:07"
    (re.compile(r"(?<=A LAS)(?=\d)"), " "),
    # Palabras conocidas pegadas por el corte de columna
    (re.compile(r"(?<=REALIZADA)(?=EN\b)"), " "),
    (re.compile(r"(?<=PERSONAS)(?=EL\b)"), " "),
    (re.compile(r"(?<=MERCANTIL)(?=EN\b)"), " "),
    # Abreviatura del banco partida por la columna: "TRANSF. RECI" + "DE LA CCE"
    (re.compile(r"TRANSF\. RECIDE"), "TRANSF. RECI DE"),
    # "HORAS" pegado a la palabra siguiente
    (re.compile(r"(?<=HORAS)(?=[A-ZÁÉÍÓÚÑ])"), " "),
]


def _repair_description(text: str) -> str:
    """Corrige artefactos de unión de líneas sin inventar contenido."""
    for pattern, replacement in _REPAIRS:
        text = pattern.sub(replacement, text)
    return text


def _join_parts(parts: list[tuple[str, bool]]) -> str:
    """Une los pedazos de una descripción respetando cortes duros de palabra."""
    if not parts:
        return ""
    out = parts[0][0]
    for index in range(1, len(parts)):
        previous_hard = parts[index - 1][1]
        out += ("" if previous_hard else " ") + parts[index][0]
    return _repair_description(out)


def _is_ledger_header(words: list[str]) -> bool:
    return "CARGOS" in words and "ABONOS" in words and "DESCRIPCION" in words


def _is_annex_header(words: list[str]) -> bool:
    return "FECHA" in words and "TR." in words and "OPERACION" in words


def _is_pos_header(words: list[str]) -> bool:
    if "TRANSACCION" in words and "REGISTRO" in words:
        return True
    return "PUNTOS" in words and "VENTA" in words and len(words) <= 4


class _LedgerState:
    """Estado del parser del libro principal (continúa entre páginas y columnas)."""

    def __init__(self, result: ParseResult) -> None:
        self.result = result
        self.current: Operation | None = None
        self.parts: list[tuple[str, bool]] = []
        self.seq = 0

    def start(self, page: int, date: str, number: str | None, raw_line: str) -> None:
        self.seq += 1
        self.current = Operation(
            page=page,
            seq=self.seq,
            date=date,
            number=number,
            description="",
            cargo=0.0,
            abono=0.0,
            igtf=0.0,
        )
        self.parts = []
        self.current.raw_lines.append(raw_line)

    def add_pieces(self, pieces: list, hard_threshold: float) -> None:
        if not pieces:
            return
        text = " ".join(token.text for token in pieces)
        hard = pieces[-1].x2 >= hard_threshold
        self.parts.append((text, hard))

    def finish(self) -> None:
        if self.current is None:
            return
        description = _join_parts(self.parts)
        self.current.description = description
        direction = "abono" if self.current.abono else "cargo"
        fields = enrich.enrich_operation(description, direction=direction)
        for key, value in fields.items():
            setattr(self.current, key, value)
        self.result.operations.append(self.current)
        if self.current.balance_printed is not None:
            self.result.checkpoints.append(
                Checkpoint(
                    page=self.current.page,
                    kind="intermedio",
                    label="saldo impreso en fila",
                    printed_balance=self.current.balance_printed,
                    op_index=len(self.result.operations) - 1,
                )
            )
        self.current = None
        self.parts = []


class MercantilCorrienteAdapter:
    name = "mercantil-corriente"
    display_name = "Mercantil — Cuenta Corriente"

    # ------------------------------------------------------------------ detección

    def detect(self, doc: fitz.Document) -> bool:
        if doc.page_count < 2:
            return False
        first = doc[0].get_text().upper()
        second = doc[1].get_text().upper() if doc.page_count > 1 else ""
        looks_like_cover = "CUENTA CORRIENTE" in re.sub(r"\s+", " ", first)
        looks_like_ledger = "MOVIMIENTOS DE CUENTA" in second and "CARGOS" in second
        is_mercantil = "MERCANTIL" in first or "MERCANTIL" in second
        return looks_like_cover and looks_like_ledger and is_mercantil

    # ------------------------------------------------------------------ público

    def parse(self, path: str | Path) -> ParseResult:
        path = Path(path)
        with fitz.open(path) as doc:
            result = ParseResult(
                path=str(path),
                file_hash=file_hash(path),
                bank=self.display_name,
                pages=doc.page_count,
                cover=self._parse_cover(doc),
            )
            self._parse_body(doc, result)
        self._compute_balances(result)
        return result

    # ------------------------------------------------------------------ resumen

    def _parse_cover(self, doc: fitz.Document) -> CoverSummary:
        cover = CoverSummary()
        lines = page_lines_raw(doc[0], 0)
        if not lines:
            return cover

        holder_lines = [
            line
            for line in lines
            if 135 <= line.y <= 205 and line.tokens and line.tokens[0].x0 < 260 and line.text.strip()
        ]
        if holder_lines:
            cover.holder = " ".join(holder_lines[0].words)

        for line in lines:
            words = line.words
            for field, keys in _AMOUNT_ROW_LABELS.items():
                if not all(key in words for key in keys):
                    continue
                if field == "otros_creditos" and "DEPOSITOS" in words:
                    continue
                if field == "otros_debitos" and "CHEQUES" in words:
                    continue
                if field == "saldo_inicio" and "FINAL" in words:
                    continue
                if field == "saldo_final" and "INICIO" in words:
                    continue
                values = [t for t in line.tokens if is_amount(t.text) and t.x0 > 600]
                if values:
                    setattr(cover, field, parse_amount(sorted(values, key=lambda t: t.x0)[-1].text))

        for index, line in enumerate(lines):
            if "NRO." in line.words and "CUENTA" in line.words:
                for candidate in lines[index + 1 : index + 3]:
                    for token in candidate.tokens:
                        if _ACCOUNT_RE.match(token.text) and len(token.text) >= 10:
                            cover.account_number = token.text
                            break
                    if cover.account_number:
                        break
                for candidate in lines[index + 1 : index + 3]:
                    dates = [t.text for t in candidate.tokens if DOTTED_DATE_RE.match(t.text)]
                    if len(dates) >= 2:
                        cover.period_start, cover.period_end = dates[0], dates[1]
                        break
                break
        return cover

    # ------------------------------------------------------------------ cuerpo

    def _parse_body(self, doc: fitz.Document, result: ParseResult) -> None:
        section = "LEDGER"
        ledger = _LedgerState(result)
        anchors_by_side: dict[str, dict[str, float]] = {}
        origins_by_side: dict[str, float] = {}
        annex_anchor: dict[str, float] = {}
        pos_anchor: dict[str, float] = {}
        section_pages: dict[str, list[int]] = {"LEDGER": [], "ANNEX": [], "POS": []}
        warned_anchor: set[tuple[int, str]] = set()

        for page_no in range(1, doc.page_count):
            page = doc[page_no]
            lines = page_lines(page, page_no)
            if not lines:
                continue

            # Pasada 1: encabezados de la página (anclas de columnas y origen)
            for line in lines:
                if _is_ledger_header(line.words):
                    fresh = find_column_anchors(line)
                    if "CARGOS" in fresh and "ABONOS" in fresh:
                        anchors_by_side[line.side] = fresh
                        origins_by_side[line.side] = min(token.x0 for token in line.tokens)

            # Borde derecho de las descripciones por columna (para unir cortes)
            split = self._split_of(lines)
            desc_rights: dict[str, float] = {}
            for side in ("L", "R"):
                anchors = anchors_by_side.get(side)
                if not anchors:
                    continue
                side_x0 = 0.0 if side == "L" else split
                desc_zone_end = min(anchors.get("CARGOS", 1e9), anchors.get("ABONOS", 1e9)) - 8
                candidates = [
                    token.x2
                    for line in lines
                    if line.side == side
                    for token in line.tokens
                    if side_x0 + 40 <= token.x0 and token.x2 <= desc_zone_end
                ]
                if candidates:
                    desc_rights[side] = max(candidates)

            # Pasada 2: máquina de secciones y filas
            for line in lines:
                words = line.words
                origin = origins_by_side.get(line.side)
                if origin is None:
                    side_xs = [t.x0 for ln in lines if ln.side == line.side for t in ln.tokens]
                    origin = min(side_xs) if side_xs else 0.0
                    origins_by_side[line.side] = origin

                if _is_annex_header(words):
                    ledger.finish()
                    section = "ANNEX"
                    annex_anchor = find_column_anchors(line)
                    section_pages["ANNEX"].append(page_no)
                    continue
                if _is_pos_header(words):
                    ledger.finish()
                    section = "POS"
                    fresh = find_column_anchors(line)
                    if "MONTO" in fresh:
                        pos_anchor = fresh
                    section_pages["POS"].append(page_no)
                    continue
                if section == "LEDGER" and _is_ledger_header(words):
                    section_pages["LEDGER"].append(page_no)
                    continue

                if section == "LEDGER":
                    if line.text.upper().strip() in ("MOVIMIENTOS DE CUENTA", "MERCANTIL EN LINEA"):
                        continue
                    anchors = anchors_by_side.get(line.side)
                    if not anchors:
                        other = anchors_by_side.get("R" if line.side == "L" else "L")
                        if other:
                            delta = split if line.side == "R" else -split
                            anchors = {key: value + delta for key, value in other.items()}
                        else:
                            key = (page_no, line.side)
                            if key not in warned_anchor:
                                warned_anchor.add(key)
                                result.fidelity_warnings.append(
                                    f"p{page_no}: sin anclas de columnas en columna {line.side}; "
                                    "montos no verificables"
                                )
                            continue
                    self._handle_ledger_line(
                        line, origin, anchors, desc_rights.get(line.side, 0.0), ledger, result
                    )
                elif section == "ANNEX":
                    self._handle_annex_line(line, origin, annex_anchor, result, section_pages)
                else:
                    if "MONTO" in words:
                        fresh = find_column_anchors(line)
                        if "MONTO" in fresh:
                            pos_anchor = fresh
                        continue
                    self._handle_pos_line(line, origin, pos_anchor, result, section_pages)

        ledger.finish()
        result.section_pages = {key: sorted(set(value)) for key, value in section_pages.items()}

    @staticmethod
    def _split_of(lines: list[Line]) -> float:
        for line in lines:
            if line.side == "R":
                return line.side_x0
        return 0.0

    # ------------------------------------------------------------------ libro

    def _handle_ledger_line(
        self,
        line: Line,
        origin: float,
        anchors: dict[str, float],
        desc_right: float,
        state: _LedgerState,
        result: ParseResult,
    ) -> None:
        tokens = line.tokens
        joined = line.text.upper()
        desc_zone_end = min(anchors.get("CARGOS", 1e9), anchors.get("ABONOS", 1e9)) - 8
        hard_threshold = (desc_right - 4.0) if desc_right else 1e9

        # saldos de inicio/fin de período impresos dentro del libro
        if "SALDO AL" in joined and ("PERIODO" in joined or "INICIO" in joined or "FINAL" in joined):
            printed: float | None = None
            for token in tokens:
                if is_amount(token.text) and classify_amount(token.x2, anchors) == "SALDO":
                    printed = parse_amount(token.text)
            kind = "inicio" if "INICIO" in joined else ("final" if "FINAL" in joined else "intermedio")
            state.finish()
            result.checkpoints.append(
                Checkpoint(page=line.page, kind=kind, label=line.text[:70], printed_balance=printed)
            )
            return

        first = tokens[0]
        is_new = bool(DATE_RE.match(first.text)) and first.x0 < origin + 30
        if is_new:
            state.finish()
            rest = tokens[1:]
            number = None
            if (
                rest
                and rest[0].text.isdigit()
                and len(rest[0].text) >= 4
                and origin + 26 <= rest[0].x0 < origin + 52
            ):
                number = rest[0].text
                rest = rest[1:]
            state.start(line.page, first.text, number, line.text)
            pieces = []
            for token in rest:
                if origin + 40 <= token.x0 and token.x2 <= desc_zone_end:
                    pieces.append(token)
                elif is_amount(token.text):
                    column = classify_amount(token.x2, anchors)
                    value = parse_amount(token.text)
                    if column == "CARGOS":
                        assert state.current is not None
                        state.current.cargo += value
                    elif column == "ABONOS":
                        assert state.current is not None
                        state.current.abono += value
                    elif column == "IMPUESTO":
                        assert state.current is not None
                        state.current.igtf += value
                    elif column == "SALDO":
                        assert state.current is not None
                        state.current.balance_printed = value
                    elif origin + 140 < token.x2 < origin + 380:
                        result.fidelity_warnings.append(
                            f"p{line.page}: monto sin columna clara ({token.text} en x={token.x2:.0f})"
                        )
            hard_threshold = (desc_right - 4.0) if desc_right else 1e9
            state.add_pieces(pieces, hard_threshold)
            return

        # continuación de descripción
        if state.current is None:
            return
        pieces = [
            token
            for token in tokens
            if origin + 40 <= token.x0 and token.x2 <= desc_zone_end
        ]
        if pieces:
            state.add_pieces(pieces, hard_threshold)
            state.current.raw_lines.append(line.text)
        for token in tokens:
            if is_amount(token.text):
                column = classify_amount(token.x2, anchors)
                if column in ("CARGOS", "ABONOS", "IMPUESTO"):
                    result.fidelity_warnings.append(
                        f"p{line.page}: monto en línea de continuación ({token.text} cerca de {column})"
                    )

    # ------------------------------------------------------------------ anexo

    def _handle_annex_line(
        self,
        line: Line,
        origin: float,
        anchors: dict[str, float],
        result: ParseResult,
        section_pages: dict[str, list[int]],
    ) -> None:
        section_pages["ANNEX"].append(line.page)
        monto_anchor = anchors.get("MONTO")
        timestamp = _TIMESTAMP_RE.search(line.text.upper())
        if timestamp:
            if result.annex:
                result.annex[-1].timestamp = f"{timestamp.group(1)} {timestamp.group(2)}"
            return

        monto_token = None
        if monto_anchor is not None:
            for token in line.tokens:
                if is_amount(token.text) and abs(token.x2 - monto_anchor) <= 14:
                    monto_token = token
        dates = [t for t in line.tokens if DATE_RE.match(t.text) and t.x0 < origin + 80]

        if monto_token is not None:
            start_x = dates[-1].x1 if dates else origin
            description = " ".join(
                token.text
                for token in line.tokens
                if token.x0 > start_x and token is not monto_token
            )
            result.annex.append(
                AnnexOperation(
                    page=line.page,
                    date_tr=dates[0].text if dates else None,
                    date_op=dates[1].text if len(dates) > 1 else (dates[0].text if dates else None),
                    description=description,
                    amount=parse_amount(monto_token.text),
                )
            )
            return

        # líneas de continuación de una operación
        if result.annex and not dates:
            text = " ".join(token.text for token in line.tokens)
            result.annex[-1].description = (result.annex[-1].description + " " + text).strip()

    # ------------------------------------------------------------------ puntos de venta

    def _handle_pos_line(
        self,
        line: Line,
        origin: float,
        anchors: dict[str, float],
        result: ParseResult,
        section_pages: dict[str, list[int]],
    ) -> None:
        section_pages["POS"].append(line.page)
        monto_anchor = anchors.get("MONTO")
        monto_token = None
        if monto_anchor is not None:
            for token in line.tokens:
                if is_amount(token.text) and abs(token.x2 - monto_anchor) <= 14:
                    monto_token = token
        dates = [t for t in line.tokens if DATE_RE.match(t.text) and t.x0 < origin + 60]
        if monto_token is None:
            if result.pos and not dates:
                last = result.pos[-1]
                text = " ".join(token.text for token in line.tokens)
                last.description = (last.description + " " + text).strip()
            return
        start_x = dates[-1].x1 if dates else origin
        description = " ".join(
            token.text
            for token in line.tokens
            if token.x0 > start_x and token is not monto_token
        )
        result.pos.append(
            PosOperation(
                page=line.page,
                date=dates[0].text if dates else None,
                description=description,
                amount=parse_amount(monto_token.text),
            )
        )

    # ------------------------------------------------------------------ saldos

    @staticmethod
    def _compute_balances(result: ParseResult) -> None:
        start: float | None = result.cover.saldo_inicio
        if start is None:
            for checkpoint in result.checkpoints:
                if checkpoint.kind == "inicio" and checkpoint.printed_balance is not None:
                    start = checkpoint.printed_balance
                    break

        running = start
        for operation in result.operations:
            if running is not None:
                running = round(running + operation.abono - operation.cargo - operation.igtf, 2)
                operation.balance_computed = running

        end = running
        for checkpoint in result.checkpoints:
            if checkpoint.kind == "inicio":
                checkpoint.computed_balance = start
            elif checkpoint.kind == "final":
                checkpoint.computed_balance = end
            elif checkpoint.op_index is not None and checkpoint.op_index < len(result.operations):
                checkpoint.computed_balance = result.operations[checkpoint.op_index].balance_computed
