"""Conciliación de un estado de cuenta contra su resumen oficial.

El banco imprime en la primera página los totales del período (créditos,
débitos, IGTF, saldo inicial y final) y dentro del libro imprime saldos
intermedios esporádicos. Cruzando todo eso se detecta:

- si el lector dejó de contar alguna fila impresa;
- si el PDF del banco omitió filas (el saldo impreso ya las incluye);
- si los anexos (MERCANTIL EN LINEA / PUNTOS DE VENTA) no cruzan con el libro.

Nunca se corrige un monto en silencio: toda diferencia queda reportada.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .model import ParseResult

TOLERANCE = 0.005


def format_amount(value: float | None) -> str:
    """Formato venezolano: 1.234.567,89."""
    if value is None:
        return "-"
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass
class Difference:
    kind: str
    expected: float | None
    parsed: float | None
    detail: str


@dataclass
class CheckpointComparison:
    page: int
    kind: str
    printed: float | None
    computed: float | None
    difference: float | None
    detail: str


@dataclass
class ReconciliationReport:
    status: str  # CUADRA | DIFERENCIAS | REVISAR
    total_cargo: float
    total_abono: float
    total_igtf: float
    computed_net: float
    expected_cargo: float | None = None
    expected_abono: float | None = None
    expected_net: float | None = None
    differences: list[Difference] = field(default_factory=list)
    missing_rows: list[Difference] = field(default_factory=list)
    checkpoints: list[CheckpointComparison] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "CUADRA"


def _bucket(amounts: list[float]) -> Counter:
    return Counter(round(value, 2) for value in amounts)


def reconcile(result: ParseResult) -> ReconciliationReport:
    cover = result.cover
    total_cargo = result.total_cargo
    total_abono = result.total_abono
    total_igtf = result.total_igtf
    computed_net = round(total_abono - total_cargo - total_igtf, 2)

    report = ReconciliationReport(
        status="REVISAR",
        total_cargo=total_cargo,
        total_abono=total_abono,
        total_igtf=total_igtf,
        computed_net=computed_net,
    )

    # --- 1. Totales contra el resumen oficial ---------------------------------
    expected_cargo = expected_abono = None
    if cover.cheques is not None and cover.otros_debitos is not None:
        expected_cargo = round(cover.cheques + cover.otros_debitos, 2)
        report.expected_cargo = expected_cargo
        if abs(total_cargo - expected_cargo) > TOLERANCE:
            report.differences.append(
                Difference(
                    kind="cargo",
                    expected=expected_cargo,
                    parsed=total_cargo,
                    detail="Débitos del libro != débitos del resumen oficial",
                )
            )
    if cover.depositos is not None and cover.otros_creditos is not None:
        expected_abono = round(cover.depositos + cover.otros_creditos, 2)
        report.expected_abono = expected_abono
        if abs(total_abono - expected_abono) > TOLERANCE:
            report.differences.append(
                Difference(
                    kind="abono",
                    expected=expected_abono,
                    parsed=total_abono,
                    detail="Créditos del libro != créditos del resumen oficial",
                )
            )
    if cover.saldo_inicio is not None and cover.saldo_final is not None:
        expected_net = round(
            cover.saldo_final - cover.saldo_inicio + (cover.igtf or 0.0), 2
        )
        report.expected_net = expected_net
        if abs(computed_net - expected_net) > TOLERANCE:
            report.differences.append(
                Difference(
                    kind="neto",
                    expected=expected_net,
                    parsed=computed_net,
                    detail="Variación neta del libro != variación de saldos del resumen",
                )
            )
    else:
        report.warnings.append("El resumen no expone saldo inicial y/o final; no se pudo verificar el neto.")

    # --- 2. Saldos intermedios impresos en el libro ---------------------------
    comparisons: list[CheckpointComparison] = []
    for checkpoint in result.checkpoints:
        if checkpoint.printed_balance is None:
            continue
        computed = checkpoint.computed_balance
        difference = (
            round(computed - checkpoint.printed_balance, 2) if computed is not None else None
        )
        comparisons.append(
            CheckpointComparison(
                page=checkpoint.page,
                kind=checkpoint.kind,
                printed=checkpoint.printed_balance,
                computed=computed,
                difference=difference,
                detail=checkpoint.label,
            )
        )
        if difference is not None and abs(difference) > TOLERANCE and checkpoint.kind not in (
            "inicio",
            "final",
        ):
            report.differences.append(
                Difference(
                    kind="saldo_intermedio",
                    expected=checkpoint.printed_balance,
                    parsed=computed,
                    detail=f"Saldo impreso en la fila de la p{checkpoint.page} no coincide con la suma local",
                )
            )
    report.checkpoints = comparisons

    # --- 3. Localización de filas omitidas por el banco ------------------------
    previous_difference = 0.0
    previous_page: int | None = None
    for comparison in comparisons:
        if comparison.difference is None:
            continue
        delta = round(comparison.difference - previous_difference, 2)
        if abs(delta) > TOLERANCE:
            if delta > 0:
                detail = (
                    "Entre estas páginas el banco debitó más de lo que imprimió "
                    f"(faltan débitos por {format_amount(delta)} Bs)"
                )
            else:
                detail = (
                    "Entre estas páginas el banco acreditó más de lo que imprimió "
                    f"(faltan créditos por {format_amount(abs(delta))} Bs)"
                )
            report.missing_rows.append(
                Difference(
                    kind="fila_omitida",
                    expected=delta,
                    parsed=None,
                    detail=f"p{previous_page or 'inicio'}–p{comparison.page}: {detail}",
                )
            )
        previous_difference = comparison.difference
        previous_page = comparison.page

    # --- 4. Cruce de anexos contra el libro -----------------------------------
    report.warnings.extend(result.fidelity_warnings)
    ledger_amounts = _bucket([op.amount for op in result.operations if op.amount])
    if result.annex:
        annex_amounts = _bucket([op.amount for op in result.annex if op.amount])
        unmatched = sum(max(0, count - ledger_amounts.get(amount, 0)) for amount, count in annex_amounts.items())
        if unmatched:
            report.warnings.append(
                f"{unmatched} operación(es) del anexo MERCANTIL EN LINEA no cruzan con el libro."
            )
    if result.pos:
        pos_amounts = _bucket([op.amount for op in result.pos if op.amount])
        unmatched = sum(max(0, count - ledger_amounts.get(amount, 0)) for amount, count in pos_amounts.items())
        if unmatched:
            report.warnings.append(
                f"{unmatched} operación(es) de PUNTOS DE VENTA no cruzan con el libro."
            )

    # --- 5. Estado final --------------------------------------------------------
    if report.differences:
        report.status = "DIFERENCIAS"
    elif report.warnings or result.warnings:
        report.status = "REVISAR"
    else:
        report.status = "CUADRA"
    return report
