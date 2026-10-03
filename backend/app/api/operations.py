"""Endpoints de operaciones: búsqueda, filtros, detalle y exportación."""

from __future__ import annotations

import csv
import io
from datetime import date as date_cls

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Operation, Statement
from ..parsers.enrich import normalize_text

router = APIRouter(prefix="/api", tags=["operations"])

SORT_FIELDS = {
    "date": Operation.date_iso,
    "amount": Operation.amount,
    "description": Operation.description,
    "method": Operation.method,
    "category": Operation.category,
}


def _filters(
    statement_id: int | None,
    date_from: str | None,
    date_to: str | None,
    direction: str | None,
    method: str | None,
    category: str | None,
    text: str | None,
    min_amount: float | None,
    max_amount: float | None,
):
    conditions = []
    if statement_id:
        conditions.append(Operation.statement_id == statement_id)
    if date_from:
        conditions.append(Operation.date_iso >= date_cls.fromisoformat(date_from))
    if date_to:
        conditions.append(Operation.date_iso <= date_cls.fromisoformat(date_to))
    if direction in ("cargo", "abono"):
        conditions.append(Operation.direction == direction)
    if method:
        conditions.append(Operation.method == method)
    if category:
        conditions.append(Operation.category == category)
    if min_amount is not None:
        conditions.append(Operation.amount >= min_amount)
    if max_amount is not None:
        conditions.append(Operation.amount <= max_amount)
    if text:
        normalized = normalize_text(text)
        if normalized:
            conditions.append(
                or_(
                    Operation.search_key.like(f"%{normalized}%"),
                    func.lower(Operation.description).like(f"%{text.lower()}%"),
                )
            )
    return conditions


@router.get("/operations")
def list_operations(
    statement_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    direction: str | None = None,
    method: str | None = None,
    category: str | None = None,
    text: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    sort: str = Query("date", pattern="^(date|amount|description|method|category)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict:
    conditions = _filters(
        statement_id, date_from, date_to, direction, method, category, text, min_amount, max_amount
    )
    total = session.scalar(select(func.count(Operation.id)).where(*conditions)) or 0
    column = SORT_FIELDS[sort]
    ordering = column.asc() if order == "asc" else column.desc()
    rows = session.scalars(
        select(Operation)
        .where(*conditions)
        .order_by(ordering.nulls_last(), Operation.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": op.id,
                "statement_id": op.statement_id,
                "date": op.date,
                "date_iso": op.date_iso.isoformat() if op.date_iso else None,
                "number": op.number,
                "description": op.description,
                "cargo": op.cargo,
                "abono": op.abono,
                "igtf": op.igtf,
                "amount": op.amount,
                "direction": op.direction,
                "method": op.method,
                "category": op.category,
                "counterpart": op.counterpart,
                "counterpart_account": op.counterpart_account,
                "counterpart_bank": op.counterpart_bank,
                "reference": op.reference,
                "concept": op.concept,
                "occurred_at": op.occurred_at,
                "phone": op.phone,
                "balance_printed": op.balance_printed,
                "balance_computed": op.balance_computed,
            }
            for op in rows
        ],
    }


@router.get("/operations/{operation_id}")
def get_operation(operation_id: int, session: Session = Depends(get_session)) -> dict:
    op = session.get(Operation, operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail="Operación no encontrada")
    statement = session.get(Statement, op.statement_id)
    return {
        "id": op.id,
        "statement_id": op.statement_id,
        "statement_file": statement.file_name if statement else None,
        "page": op.page,
        "date": op.date,
        "date_iso": op.date_iso.isoformat() if op.date_iso else None,
        "number": op.number,
        "description": op.description,
        "cargo": op.cargo,
        "abono": op.abono,
        "igtf": op.igtf,
        "amount": op.amount,
        "direction": op.direction,
        "method": op.method,
        "category": op.category,
        "counterpart": op.counterpart,
        "counterpart_account": op.counterpart_account,
        "counterpart_bank": op.counterpart_bank,
        "reference": op.reference,
        "concept": op.concept,
        "occurred_at": op.occurred_at,
        "phone": op.phone,
        "balance_printed": op.balance_printed,
        "balance_computed": op.balance_computed,
    }


@router.get("/export.csv")
def export_csv(
    statement_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    direction: str | None = None,
    method: str | None = None,
    category: str | None = None,
    text: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    conditions = _filters(
        statement_id, date_from, date_to, direction, method, category, text, min_amount, max_amount
    )
    rows = session.scalars(
        select(Operation).where(*conditions).order_by(Operation.date_iso.asc(), Operation.id.asc())
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "fecha",
            "numero",
            "descripcion",
            "cargo",
            "abono",
            "igtf",
            "metodo",
            "categoria",
            "contraparte",
            "cuenta_contraparte",
            "banco_contraparte",
            "referencia",
            "concepto",
            "ocurrido_en",
        ]
    )
    for op in rows:
        writer.writerow(
            [
                op.date_iso or op.date,
                op.number or "",
                op.description,
                f"{op.cargo:.2f}".replace(".", ","),
                f"{op.abono:.2f}".replace(".", ","),
                f"{op.igtf:.2f}".replace(".", ","),
                op.method,
                op.category,
                op.counterpart or "",
                op.counterpart_account or "",
                op.counterpart_bank or "",
                op.reference or "",
                op.concept or "",
                op.occurred_at or "",
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="movimientos.csv"'},
    )
