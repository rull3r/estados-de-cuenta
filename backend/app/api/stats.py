"""Endpoints de estadísticas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_session
from ..services.stats import biggest_operations, find_duplicates, summary

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary")
def get_summary(
    statement_id: int | None = None,
    session: Session = Depends(get_session),
) -> dict:
    return summary(session, statement_id)


@router.get("/biggest")
def get_biggest(
    statement_id: int | None = None,
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> list[dict]:
    return biggest_operations(session, statement_id, limit)


@router.get("/duplicates")
def get_duplicates(
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[dict]:
    """Operaciones que aparecen en más de un estado de cuenta (posibles repetidas)."""
    return find_duplicates(session, limit)
