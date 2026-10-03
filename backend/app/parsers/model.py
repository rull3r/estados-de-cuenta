"""Estructuras de datos del parseo, neutrales al banco."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Operation:
    """Movimiento del libro principal (sección MOVIMIENTOS DE CUENTA)."""

    page: int
    seq: int
    date: str  # dd/mm tal como aparece impreso
    number: str | None
    description: str
    cargo: float
    abono: float
    igtf: float
    balance_printed: float | None = None  # saldo impreso en la propia fila (si existe)
    balance_computed: float | None = None  # saldo calculado al sumar en orden
    raw_lines: list[str] = field(default_factory=list)

    # Campos enriquecidos
    method: str = "otro"
    counterpart: str | None = None
    counterpart_account: str | None = None
    counterpart_bank: str | None = None
    reference: str | None = None
    concept: str | None = None
    occurred_at: str | None = None
    phone: str | None = None

    @property
    def search_key(self) -> str:
        from .enrich import normalize_text

        return normalize_text(self.description)

    @property
    def amount(self) -> float:
        return self.abono if self.abono else self.cargo


@dataclass
class Checkpoint:
    """Saldo impreso por el banco dentro del libro (inicio, fin o intermedio)."""

    page: int
    kind: str  # inicio | final | intermedio
    label: str
    printed_balance: float | None = None
    op_index: int | None = None  # operación tras la cual se imprimió (intermedio)
    computed_balance: float | None = None


@dataclass
class AnnexOperation:
    """Operación listada en el anexo MERCANTIL EN LINEA."""

    page: int
    date_tr: str | None
    date_op: str | None
    description: str
    amount: float | None
    timestamp: str | None = None


@dataclass
class PosOperation:
    """Operación listada en la sección PUNTOS DE VENTA."""

    page: int
    date: str | None
    description: str
    amount: float | None


@dataclass
class CoverSummary:
    """Resumen oficial impreso en la primera página."""

    holder: str | None = None
    account_number: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    saldo_inicio: float | None = None
    depositos: float | None = None
    otros_creditos: float | None = None
    cheques: float | None = None
    otros_debitos: float | None = None
    igtf: float | None = None
    saldo_final: float | None = None


@dataclass
class ParseResult:
    """Resultado completo del parseo de un estado de cuenta."""

    path: str
    file_hash: str
    bank: str
    pages: int
    cover: CoverSummary
    operations: list[Operation] = field(default_factory=list)
    annex: list[AnnexOperation] = field(default_factory=list)
    pos: list[PosOperation] = field(default_factory=list)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fidelity_warnings: list[str] = field(default_factory=list)
    section_pages: dict[str, list[int]] = field(default_factory=dict)

    @property
    def total_cargo(self) -> float:
        return round(sum(op.cargo for op in self.operations), 2)

    @property
    def total_abono(self) -> float:
        return round(sum(op.abono for op in self.operations), 2)

    @property
    def total_igtf(self) -> float:
        return round(sum(op.igtf for op in self.operations), 2)
