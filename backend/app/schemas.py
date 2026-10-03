"""Esquemas de entrada para la API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdjustmentIn(BaseModel):
    date: str = Field(pattern=r"^\d{2}/\d{2}(/\d{2,4})?$")
    description: str = Field(min_length=1, max_length=400)
    amount: float = Field(gt=0)
    direction: str = Field(pattern=r"^(cargo|abono)$")
    note: str | None = Field(default=None, max_length=400)


class RuleIn(BaseModel):
    pattern: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=60)
    priority: int = Field(default=100, ge=0, le=999)


class RuleOut(RuleIn):
    id: int
