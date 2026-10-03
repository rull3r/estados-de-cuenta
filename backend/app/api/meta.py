"""Endpoints auxiliares: salud, bancos, categorías y reglas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_session
from ..models import CategoryRule, Operation
from ..schemas import RuleIn, RuleOut
from ..services.categories import DEFAULT_CATEGORIES
from ..services.importer import reapply_categories

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


@router.get("/banks")
def banks() -> list[dict]:
    return config.ALLOWED_BANKS


@router.get("/categories")
def categories(session: Session = Depends(get_session)) -> dict:
    used = [
        row
        for row in session.scalars(
            select(Operation.category).distinct().order_by(Operation.category)
        ).all()
        if row
    ]
    known = sorted(set(used) | set(DEFAULT_CATEGORIES.values()))
    return {"categories": known}


@router.get("/rules", response_model=list[RuleOut])
def list_rules(session: Session = Depends(get_session)) -> list[CategoryRule]:
    return list(session.scalars(select(CategoryRule).order_by(CategoryRule.priority, CategoryRule.id)))


@router.post("/rules", response_model=RuleOut, status_code=201)
def create_rule(payload: RuleIn, session: Session = Depends(get_session)) -> CategoryRule:
    rule = CategoryRule(pattern=payload.pattern, category=payload.category, priority=payload.priority)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    reapply_categories(session)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, session: Session = Depends(get_session)) -> None:
    rule = session.get(CategoryRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    session.delete(rule)
    session.commit()
    reapply_categories(session)
