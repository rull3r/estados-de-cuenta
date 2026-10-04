"""Importación de estados de cuenta a la base de datos."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict
from datetime import date as date_cls
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import AnnexOperation, CategoryRule, Issue, Operation, PosOperation, Statement
from ..parsers.base import parse_file
from ..parsers.enrich import normalize_text
from ..parsers.model import ParseResult
from ..parsers.reconcile import reconcile
from .categories import DEFAULT_CATEGORIES, categorizer

MONTHS_ES = {
    "01": "Enero",
    "02": "Febrero",
    "03": "Marzo",
    "04": "Abril",
    "05": "Mayo",
    "06": "Junio",
    "07": "Julio",
    "08": "Agosto",
    "09": "Septiembre",
    "10": "Octubre",
    "11": "Noviembre",
    "12": "Diciembre",
}


class DuplicateStatementError(RuntimeError):
    def __init__(self, statement_id: int) -> None:
        super().__init__("El archivo ya fue cargado")
        self.statement_id = statement_id


# SQLite admite un solo escritor a la vez: los procesamientos se serializan para
# que subir varios PDFs en ráfaga nunca produzca "database is locked".
_PROCESS_LOCK = threading.Lock()


def _period_iso(period: str | None) -> date_cls | None:
    """Convierte un período dd-mm-yy a fecha ISO."""
    if not period:
        return None
    try:
        day, month, year = period.split("-")
        full_year = int(year) + (2000 if int(year) < 100 else 0)
        return date_cls(full_year, int(month), int(day))
    except ValueError:
        return None


def _period_month(period_start: str | None, period_end: str | None) -> tuple[int, int]:
    """Devuelve (año, mes) del período a partir de dd-mm-yy."""
    reference = period_end or period_start
    if not reference:
        return 0, 0
    try:
        day, month, year = reference.split("-")
        full_year = int(year) + (2000 if int(year) < 100 else 0)
        return full_year, int(month)
    except ValueError:
        return 0, 0


def resolve_date_iso(date: str, year: int, month: int) -> str | None:
    """Convierte 'dd/mm' del libro a ISO teniendo en cuenta el cambio de año."""
    try:
        day_s, month_s = date.split("/")
        resolved_year = year
        if month == 1 and int(month_s) == 12:
            resolved_year = year - 1
        elif month == 12 and int(month_s) == 1:
            resolved_year = year + 1
        return f"{resolved_year:04d}-{int(month_s):02d}-{int(day_s):02d}"
    except (ValueError, AttributeError):
        return None


def persist_parse(session: Session, statement: Statement, result: ParseResult) -> None:
    """Guarda operaciones, anexos, POS e incidencias de conciliación."""
    report = reconcile(result)
    year, month = _period_month(result.cover.period_start, result.cover.period_end)
    if year == 0:
        year, month = 2000, 1

    rules = list(session.scalars(select(CategoryRule).order_by(CategoryRule.priority, CategoryRule.id)))
    statements_rules = [(normalize_text(rule.pattern), rule.category) for rule in rules]

    def category_for(method: str, search_key: str) -> str:
        return categorizer(method, search_key, statements_rules)

    session.execute(delete(Operation).where(Operation.statement_id == statement.id))
    for operation in result.operations:
        search_key = normalize_text(operation.description)
        iso = resolve_date_iso(operation.date, year, month)
        session.add(
            Operation(
                statement_id=statement.id,
                page=operation.page,
                seq=operation.seq,
                date=operation.date,
                date_iso=date_cls.fromisoformat(iso) if iso else None,
                number=operation.number,
                description=operation.description,
                search_key=search_key,
                cargo=operation.cargo,
                abono=operation.abono,
                igtf=operation.igtf,
                amount=operation.amount,
                direction="abono" if operation.abono else "cargo",
                method=operation.method,
                category=category_for(operation.method, search_key),
                counterpart=operation.counterpart,
                counterpart_account=operation.counterpart_account,
                counterpart_bank=operation.counterpart_bank,
                reference=operation.reference,
                concept=operation.concept,
                occurred_at=operation.occurred_at,
                phone=operation.phone,
                balance_printed=operation.balance_printed,
                balance_computed=operation.balance_computed,
            )
        )

    for item in result.annex:
        session.add(
            AnnexOperation(
                statement_id=statement.id,
                page=item.page,
                date_tr=item.date_tr,
                date_op=item.date_op,
                description=item.description,
                amount=item.amount,
                timestamp=item.timestamp,
            )
        )
    for item in result.pos:
        session.add(
            PosOperation(
                statement_id=statement.id,
                page=item.page,
                date=item.date,
                description=item.description,
                amount=item.amount,
            )
        )
    for difference in report.differences:
        session.add(
            Issue(
                statement_id=statement.id,
                kind=difference.kind,
                detail=difference.detail,
                expected=difference.expected,
                parsed=difference.parsed,
            )
        )
    for missing in report.missing_rows:
        session.add(
            Issue(
                statement_id=statement.id,
                kind="fila_omitida",
                detail=missing.detail,
                expected=missing.expected,
                parsed=missing.parsed,
            )
        )
    for warning in report.warnings:
        session.add(Issue(statement_id=statement.id, kind="advertencia", detail=warning))

    statement.holder = result.cover.holder
    statement.account_number = result.cover.account_number
    statement.period_start = result.cover.period_start
    statement.period_end = result.cover.period_end
    statement.saldo_inicio = result.cover.saldo_inicio
    statement.saldo_final = result.cover.saldo_final
    statement.total_cargo = report.total_cargo
    statement.total_abono = report.total_abono
    statement.total_igtf = report.total_igtf
    statement.transaction_count = len(result.operations)
    statement.annex_count = len(result.annex)
    statement.pos_count = len(result.pos)
    statement.pages = result.pages
    statement.status = report.status
    statement.error = None

    # Aviso si el período se solapa con otro estado ya cargado de la misma cuenta
    start = _period_iso(statement.period_start)
    end = _period_iso(statement.period_end)
    if start and end and statement.account_number:
        others = session.scalars(
            select(Statement).where(
                Statement.id != statement.id,
                Statement.account_number == statement.account_number,
            )
        ).all()
        for other in others:
            other_start = _period_iso(other.period_start)
            other_end = _period_iso(other.period_end)
            if other_start and other_end and start <= other_end and other_start <= end:
                session.add(
                    Issue(
                        statement_id=statement.id,
                        kind="advertencia",
                        detail=(
                            f"El período se solapa con «{other.file_name}» "
                            f"({other.period_start} a {other.period_end}); "
                            "puede haber operaciones repetidas entre ambos."
                        ),
                    )
                )

    statement.report_json = json.dumps(
        {
            "status": report.status,
            "background": result.bank,
            "year": year,
            "month": month,
            "month_name": MONTHS_ES.get(f"{month:02d}", ""),
            "expected_cargo": report.expected_cargo,
            "expected_abono": report.expected_abono,
            "expected_net": report.expected_net,
            "computed_net": report.computed_net,
            "differences": [asdict(d) for d in report.differences],
            "missing_rows": [asdict(m) for m in report.missing_rows],
            "checkpoints": [asdict(c) for c in report.checkpoints],
            "warnings": report.warnings,
            "fidelity_warnings": result.fidelity_warnings,
        },
        ensure_ascii=False,
    )


def _set_progress(session: Session, statement: Statement, stage: str, percent: int) -> None:
    statement.progress_stage = stage
    statement.progress_percent = percent
    session.commit()


def process_statement(statement_id: int, path: str) -> None:
    """Tarea de fondo: parsea el PDF y llena la base de datos.

    Se serializa con un lock porque SQLite admite un solo escritor a la vez; así
    subir varios estados de cuenta en ráfaga no produce «database is locked».
    Reporta el avance (etapa, porcentaje y página) para que la web lo muestre.
    """
    with _PROCESS_LOCK:
        session = SessionLocal()
        try:
            statement = session.get(Statement, statement_id)
            if statement is None:
                return
            try:
                statement.started_at = datetime.utcnow()
                _set_progress(session, statement, "abriendo PDF", 2)

                last_update = [0.0]

                def on_page(page: int, total: int) -> None:
                    now = time.monotonic()
                    if page < total and now - last_update[0] < 0.8:
                        return
                    last_update[0] = now
                    percent = 3 + int(84 * page / max(total, 1))
                    _set_progress(session, statement, f"leyendo páginas ({page}/{total})", percent)

                result = parse_file(path, progress_callback=on_page)
                _set_progress(session, statement, "conciliando contra el resumen", 90)
                persist_parse(session, statement, result)
                statement.progress_stage = "guardando en la base"
                statement.progress_percent = 96
                session.commit()
                statement.progress_stage = "listo"
                statement.progress_percent = 100
                statement.finished_at = datetime.utcnow()
                session.commit()
            except Exception as error:  # noqa: BLE001
                session.rollback()
                statement = session.get(Statement, statement_id)
                if statement is not None:
                    statement.status = "error"
                    statement.error = str(error)
                    statement.progress_stage = "error"
                    statement.finished_at = datetime.utcnow()
                    session.commit()
        finally:
            session.close()


def recover_interrupted() -> int:
    """Reencola los estados que quedaron «procesando» tras un reinicio.

    Si el PDF original sigue en disco se vuelve a procesar automáticamente; si no,
    el estado pasa a «error» con un mensaje claro para poder reintentar la subida.
    Devuelve cuántos se reencolaron.
    """
    session = SessionLocal()
    recovered = 0
    try:
        stale = session.scalars(select(Statement).where(Statement.status == "procesando")).all()
        for statement in stale:
            path = statement.source_path
            if path and Path(path).exists():
                statement.progress_stage = "en cola"
                statement.progress_percent = 0
                statement.started_at = None
                threading.Thread(
                    target=process_statement,
                    args=(statement.id, path),
                    daemon=True,
                    name=f"edc-recover-{statement.id}",
                ).start()
                recovered += 1
            else:
                statement.status = "error"
                statement.error = (
                    "El procesamiento se interrumpió (reinicio) y no se encontró el archivo; "
                    "vuelve a subirlo."
                )
                statement.progress_stage = "error"
        session.commit()
    finally:
        session.close()
    return recovered


def statement_to_dict(
    statement: Statement, *, detail: bool = False, queue_position: int | None = None
) -> dict:
    payload = {
        "id": statement.id,
        "bank": statement.bank,
        "file_name": statement.file_name,
        "pages": statement.pages,
        "uploaded_at": statement.uploaded_at.isoformat(),
        "status": statement.status,
        "error": statement.error,
        "progress_stage": statement.progress_stage,
        "progress_percent": statement.progress_percent,
        "started_at": statement.started_at.isoformat() if statement.started_at else None,
        "finished_at": statement.finished_at.isoformat() if statement.finished_at else None,
        "queue_position": queue_position,
        "holder": statement.holder,
        "account_number": statement.account_number,
        "period_start": statement.period_start,
        "period_end": statement.period_end,
        "saldo_inicio": statement.saldo_inicio,
        "saldo_final": statement.saldo_final,
        "total_cargo": statement.total_cargo,
        "total_abono": statement.total_abono,
        "total_igtf": statement.total_igtf,
        "transaction_count": statement.transaction_count,
        "annex_count": statement.annex_count,
        "pos_count": statement.pos_count,
    }
    if detail:
        payload["report"] = json.loads(statement.report_json) if statement.report_json else None
        payload["issues"] = [
            {
                "id": issue.id,
                "kind": issue.kind,
                "detail": issue.detail,
                "expected": issue.expected,
                "parsed": issue.parsed,
            }
            for issue in statement.issues
        ]
        payload["adjustments"] = [
            {
                "id": adjustment.id,
                "date": adjustment.date,
                "description": adjustment.description,
                "amount": adjustment.amount,
                "direction": adjustment.direction,
                "note": adjustment.note,
            }
            for adjustment in statement.adjustments
        ]
    return payload


def reapply_categories(session: Session) -> None:
    """Reaplica reglas de categoría a todas las operaciones."""
    rules = list(session.scalars(select(CategoryRule).order_by(CategoryRule.priority, CategoryRule.id)))
    rules_normalized = [(normalize_text(rule.pattern), rule.category) for rule in rules]
    for operation in session.scalars(select(Operation)):
        operation.category = categorizer(operation.method, operation.search_key, rules_normalized)
    session.commit()


__all__ = [
    "DEFAULT_CATEGORIES",
    "DuplicateStatementError",
    "persist_parse",
    "process_statement",
    "reapply_categories",
    "resolve_date_iso",
    "statement_to_dict",
]
