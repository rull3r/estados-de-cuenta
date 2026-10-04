"""Estadísticas agregadas sobre las operaciones."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Adjustment, Operation, Statement
from .importer import _period_iso


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
        )
    ).all()
    # Serie cronológica ascendente (dd-mm-yy no se ordena como texto).
    monthly_rows = sorted(
        monthly_rows,
        key=lambda row: (_period_iso(row[1]) or date.min, row[0]),
    )

    # --- flujo por día (con saldo de cierre de cada día) ---
    by_day_rows = session.execute(
        select(
            Operation.date_iso,
            func.coalesce(func.sum(Operation.cargo), 0.0),
            func.coalesce(func.sum(Operation.abono), 0.0),
            func.count(Operation.id),
        )
        .where(where, Operation.date_iso.is_not(None))
        .group_by(Operation.date_iso)
        .order_by(Operation.date_iso)
    ).all()
    day_balances: dict = {}
    for date_iso, balance in session.execute(
        select(Operation.date_iso, Operation.balance_computed)
        .where(where, Operation.date_iso.is_not(None), Operation.balance_computed.is_not(None))
        .order_by(Operation.date_iso, Operation.statement_id, Operation.seq)
    ).all():
        day_balances[date_iso] = balance
    by_day = [
        {
            "date": row[0].isoformat() if row[0] else None,
            "cargo": row[1],
            "abono": row[2],
            "count": row[3],
            "balance": day_balances.get(row[0]),
        }
        for row in by_day_rows
    ]

    # --- costos bancarios (comisiones, mantenimiento, impuestos) ---
    cost_methods = (
        "comision",
        "comision_pago_movil",
        "comision_credito_inmediato",
        "mantenimiento",
        "emision_estado",
        "mensajeria",
        "impuesto",
    )
    cost_rows = session.execute(
        select(Operation.method, func.coalesce(func.sum(Operation.cargo), 0.0))
        .where(where, Operation.method.in_(cost_methods))
        .group_by(Operation.method)
        .order_by(func.sum(Operation.cargo).desc())
    ).all()
    bank_costs = {
        "total": round(sum(value for _, value in cost_rows) + totals[2], 2),
        "items": [{"label": method, "value": value} for method, value in cost_rows],
        "igtf": totals[2],
    }

    # --- promedios y extremos ---
    averages = session.execute(
        select(
            func.coalesce(func.avg(Operation.amount), 0.0),
            func.coalesce(func.max(Operation.cargo), 0.0),
            func.coalesce(func.max(Operation.abono), 0.0),
            func.count(func.distinct(Operation.date_iso)),
        ).where(where)
    ).one()
    active_days = averages[3] or 0
    averages_payload = {
        "ticket": round(averages[0], 2),
        "max_cargo": averages[1],
        "max_abono": averages[2],
        "days": active_days,
        "daily_cargo": round(totals[0] / active_days, 2) if active_days else 0.0,
        "daily_abono": round(totals[1] / active_days, 2) if active_days else 0.0,
    }

    # --- comportamiento por día de la semana ---
    weekday_rows = session.execute(
        select(
            func.strftime("%w", Operation.date_iso),
            func.coalesce(func.sum(Operation.cargo), 0.0),
            func.coalesce(func.sum(Operation.abono), 0.0),
            func.count(Operation.id),
        )
        .where(where, Operation.date_iso.is_not(None))
        .group_by(func.strftime("%w", Operation.date_iso))
    ).all()
    weekday_names = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
    by_weekday = [
        {
            "label": weekday_names[int(row[0])] if row[0] is not None else "?",
            "cargo": row[1],
            "abono": row[2],
            "count": row[3],
        }
        for row in sorted(weekday_rows, key=lambda row: row[0] or "0")
    ]

    # --- días con más gasto ---
    top_day_rows = session.execute(
        select(
            Operation.date_iso,
            func.coalesce(func.sum(Operation.cargo), 0.0),
            func.count(Operation.id),
        )
        .where(where, Operation.date_iso.is_not(None))
        .group_by(Operation.date_iso)
        .order_by(func.sum(Operation.cargo).desc())
        .limit(5)
    ).all()
    top_days = [
        {
            "date": row[0].isoformat() if row[0] else None,
            "cargo": row[1],
            "count": row[2],
        }
        for row in top_day_rows
    ]

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
        "by_day": by_day,
        "bank_costs": bank_costs,
        "averages": averages_payload,
        "by_weekday": by_weekday,
        "top_days": top_days,
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


def find_duplicates(session: Session, limit: int = 50) -> list[dict]:
    """Operaciones que aparecen en más de un estado de cuenta.

    Se consideran repetidas si comparten monto, fecha, sentido y la misma
    referencia o cuenta de contraparte (los períodos de Mercantil pueden solaparse
    y traer operaciones del mes anterior).
    """
    key_columns = (
        Operation.amount,
        Operation.date_iso,
        Operation.direction,
        func.coalesce(Operation.reference, ""),
        func.coalesce(Operation.counterpart_account, ""),
    )
    groups = session.execute(
        select(
            *key_columns,
            func.count(Operation.id),
            func.count(func.distinct(Operation.statement_id)),
        )
        .group_by(*key_columns)
        .having(func.count(func.distinct(Operation.statement_id)) > 1)
        .order_by(
            func.count(func.distinct(Operation.statement_id)).desc(),
            func.count(Operation.id).desc(),
        )
        .limit(limit)
    ).all()

    results: list[dict] = []
    for amount, date_iso, direction, reference, account, count, statement_count in groups:
        rows = session.execute(
            select(Operation, Statement.file_name)
            .join(Statement, Operation.statement_id == Statement.id)
            .where(
                Operation.amount == amount,
                Operation.date_iso == date_iso,
                Operation.direction == direction,
                func.coalesce(Operation.reference, "") == reference,
                func.coalesce(Operation.counterpart_account, "") == account,
            )
            .order_by(Operation.statement_id, Operation.seq)
        ).all()
        results.append(
            {
                "amount": amount,
                "date_iso": date_iso.isoformat() if date_iso else None,
                "direction": direction,
                "reference": reference or None,
                "counterpart_account": account or None,
                "count": count,
                "statement_count": statement_count,
                "operations": [
                    {
                        "id": operation.id,
                        "statement_id": operation.statement_id,
                        "statement_file": file_name,
                        "date": operation.date,
                        "description": operation.description,
                        "counterpart": operation.counterpart,
                    }
                    for operation, file_name in rows
                ],
            }
        )
    return results
