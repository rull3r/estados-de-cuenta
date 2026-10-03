"""Modelos ORM."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bank: Mapped[str] = mapped_column(String(60))
    file_name: Mapped[str] = mapped_column(String(300))
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    status: Mapped[str] = mapped_column(String(20), default="procesando")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    holder: Mapped[str | None] = mapped_column(String(200), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    period_start: Mapped[str | None] = mapped_column(String(20), nullable=True)
    period_end: Mapped[str | None] = mapped_column(String(20), nullable=True)

    saldo_inicio: Mapped[float | None] = mapped_column(Float, nullable=True)
    saldo_final: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_cargo: Mapped[float] = mapped_column(Float, default=0.0)
    total_abono: Mapped[float] = mapped_column(Float, default=0.0)
    total_igtf: Mapped[float] = mapped_column(Float, default=0.0)
    transaction_count: Mapped[int] = mapped_column(Integer, default=0)
    annex_count: Mapped[int] = mapped_column(Integer, default=0)
    pos_count: Mapped[int] = mapped_column(Integer, default=0)

    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    operations: Mapped[list[Operation]] = relationship(
        back_populates="statement", cascade="all, delete-orphan"
    )
    issues: Mapped[list[Issue]] = relationship(
        back_populates="statement", cascade="all, delete-orphan"
    )
    adjustments: Mapped[list[Adjustment]] = relationship(
        back_populates="statement", cascade="all, delete-orphan"
    )


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id", ondelete="CASCADE"), index=True)
    page: Mapped[int] = mapped_column(Integer, default=0)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[str] = mapped_column(String(10))
    date_iso: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    search_key: Mapped[str] = mapped_column(Text, index=True)
    cargo: Mapped[float] = mapped_column(Float, default=0.0)
    abono: Mapped[float] = mapped_column(Float, default=0.0)
    igtf: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    direction: Mapped[str] = mapped_column(String(10), default="cargo")
    method: Mapped[str] = mapped_column(String(40), default="otro", index=True)
    category: Mapped[str] = mapped_column(String(60), default="Otros", index=True)
    counterpart: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    counterpart_account: Mapped[str | None] = mapped_column(String(40), nullable=True)
    counterpart_bank: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(60), nullable=True)
    concept: Mapped[str | None] = mapped_column(String(200), nullable=True)
    occurred_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    balance_printed: Mapped[float | None] = mapped_column(Float, nullable=True)
    balance_computed: Mapped[float | None] = mapped_column(Float, nullable=True)

    statement: Mapped[Statement] = relationship(back_populates="operations")

    __table_args__ = (
        Index("ix_operations_stmt_date", "statement_id", "date_iso"),
        Index("ix_operations_stmt_method", "statement_id", "method"),
    )


class AnnexOperation(Base):
    __tablename__ = "annex_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id", ondelete="CASCADE"), index=True)
    page: Mapped[int] = mapped_column(Integer, default=0)
    date_tr: Mapped[str | None] = mapped_column(String(10), nullable=True)
    date_op: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[str | None] = mapped_column(String(30), nullable=True)


class PosOperation(Base):
    __tablename__ = "pos_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id", ondelete="CASCADE"), index=True)
    page: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text)
    expected: Mapped[float | None] = mapped_column(Float, nullable=True)
    parsed: Mapped[float | None] = mapped_column(Float, nullable=True)

    statement: Mapped[Statement] = relationship(back_populates="issues")


class Adjustment(Base):
    __tablename__ = "adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id", ondelete="CASCADE"), index=True)
    date: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(10), default="cargo")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    statement: Mapped[Statement] = relationship(back_populates="adjustments")


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60))
    priority: Mapped[int] = mapped_column(Integer, default=100)
