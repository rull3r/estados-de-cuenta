"""Estadísticas agregadas sobre las operaciones."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Adjustment, Operation, Statement


def _scope(statement_id: int | None):
    if statement_id:
        return Operation.statement_id == statement_id
    return Operation.id.is_not(None)


def summary(session: Session, statement_id: int | None = None) -> dict:
    where = _scope(statement_id)

    totals = session.execute(
        select(
            func.coalesce(func.sum(Operation.cargo), 0.0),
            func.coalesce(func.sum(Operation.abono), 0.0),
            func.coalesce(func.sum(Operation.igtf), 0.0),
            func.count(Operation.id),
        ).where(where)
    ).one()

    def grouped(column, limit: int = 50):
        rows = session.execute(
            select(
                column,
                func.count(Operation.id),
                func.coalesce(func.sum(Operation.cargo), 0.0),
                func.coalesce(func.sum(Operation.abono), 0.0),
            )
            .where(where)
            .group_by(column)
            .order_by(func.count(Operation.id).desc())
            .limit(limit)
        ).all()
        return [
            {"label": label or "Sin dato", "count": count, "cargo": cargo, "abono": abono}
            for label, count, cargo, abono in rows
        ]

    def tops(column):
        cargo_rows = session.execute(
            select(column, func.count(Operation.id), func.coalesce(func.sum(Operation.cargo), 0.0))
            .where(where, Operation.cargo > 0, column.is_not(None))
            .group_by(column)
            .order_by(func.sum(Operation.cargo).desc())
            .limit(8)
        ).all()
        abono_rows = session.execute(
            select(column, func.count(Operation.id), func.coalesce(func.sum(Operation.abono), 0.0))
            .where(where, Operation.abono > 0, column.is_not(None))
            .group_by(column)
            .order_by(func.sum(Operation.abono).desc())
            .limit(8)
        ).all()
        return {
            "cargo": [{"label": r[0], "count": r[1], "total": r[2]} for r in cargo_rows],
            "abono": [{"label": r[0], "count": r[1], "total": r[2]} for r in abono_rows],
        }

    adjustments = session.execute(
        select(
            func.coalesce(func.sum(func.iif(Adjustment.direction == "cargo", Adjustment.amount, 0.0)), 0.0),
            func.coalesce(func.sum(func.iif(Adjustment.direction == "abono", Adjustment.amount, 0.0)), 0.0),
        ).where(Adjustment.statement_id == statement_id if statement_id else Adjustment.id.is_not(None))
    ).one()

    monthly_rows = session.execute(
        select(
            Statement.id,
            Statement.period_start,
            Statement.period_end,
            Statement.total_cargo,
            Statement.total_abono,
            Statement.saldo_inicio,
            Statement.saldo_final,
            Statement.transaction_count,
            Statement.status,
        ).order_by(Statement.period_start)
    ).all()

    return {
        "total_cargo": totals[0],
        "total_abono": totals[1],
        "total_igtf": totals[2],
        "count": totals[3],
        "net": round(totals[1] - totals[0] - totals[2], 2),
        "by_method": grouped(Operation.method),
        "by_category": grouped(Operation.category),
        "top_counterparts": tops(Operation.counterpart),
        "top_concepts": tops(Operation.concept),
        "adjustments": {"cargo": adjustments[0], "abono": adjustments[1]},
        "monthly": [
            {
                "statement_id": row[0],
                "period_start": row[1],
                "period_end": row[2],
                "cargo": row[3],
                "abono": row[4],
                "saldo_inicio": row[5],
                "saldo_final": row[6],
                "count": row[7],
                "status": row[8],
            }
            for row in monthly_rows
        ],
    }


def biggest_operations(session: Session, statement_id: int | None = None, limit: int = 10) -> list[dict]:
    rows = session.execute(
        select(Operation)
        .where(_scope(statement_id), Operation.amount > 0)
        .order_by(Operation.amount.desc())
        .limit(limit)
    ).scalars()
    return [
        {
            "id": op.id,
            "date": op.date,
            "date_iso": op.date_iso.isoformat() if op.date_iso else None,
            "description": op.description,
            "method": op.method,
            "category": op.category,
            "cargo": op.cargo,
            "abono": op.abono,
            "amount": op.amount,
            "counterpart": op.counterpart,
        }
        for op in rows
    ]
