"""CLI de estados-de-cuenta.

Uso:
    python -m app.cli parse <archivo.pdf> [--json salida.json] [--csv salida.csv]
    python -m app.cli validate <archivo|directorio|glob> [...]
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .parsers.base import UnsupportedBankError, parse_file
from .parsers.model import ParseResult
from .parsers.reconcile import ReconciliationReport, reconcile

STATUS_MARK = {"CUADRA": "[OK]", "DIFERENCIAS": "[!]", "REVISAR": "[?]"}


def _money(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _report_text(result: ParseResult, report: ReconciliationReport) -> str:
    lines: list[str] = []
    cover = result.cover
    lines.append("=" * 78)
    lines.append(f"ARCHIVO   : {Path(result.path).name}")
    lines.append(f"BANCO     : {result.bank}")
    lines.append(f"TITULAR   : {cover.holder or '-'}")
    lines.append(f"CUENTA    : {cover.account_number or '-'}")
    lines.append(
        f"PERIODO   : {cover.period_start or '-'} a {cover.period_end or '-'} "
        f"({result.pages} páginas)"
    )
    lines.append("-" * 78)
    lines.append(f"Movimientos del libro : {len(result.operations)}")
    lines.append(f"Anexo Mercantil       : {len(result.annex)}")
    lines.append(f"Puntos de venta       : {len(result.pos)}")
    lines.append("-" * 78)
    lines.append(f"Cargos (libro)        : {_money(report.total_cargo)}")
    lines.append(f"Abonos (libro)        : {_money(report.total_abono)}")
    lines.append(f"IGTF (libro)          : {_money(report.total_igtf)}")
    lines.append(f"Neto (libro)          : {_money(report.computed_net)}")
    if report.expected_cargo is not None:
        lines.append(f"Cargos (resumen)      : {_money(report.expected_cargo)}")
    if report.expected_abono is not None:
        lines.append(f"Abonos (resumen)      : {_money(report.expected_abono)}")
    if report.expected_net is not None:
        lines.append(f"Neto esperado         : {_money(report.expected_net)}")
    lines.append("-" * 78)

    if report.differences:
        lines.append("DIFERENCIAS DETECTADAS:")
        for difference in report.differences:
            lines.append(f"  - {difference.detail}")
            if difference.expected is not None and difference.parsed is not None:
                delta = difference.parsed - difference.expected
                lines.append(
                    f"      esperado {_money(difference.expected)} / leído "
                    f"{_money(difference.parsed)} / delta {_money(delta)}"
                )
    if report.missing_rows:
        lines.append("FILAS OMITIDAS POR EL BANCO (deducidas del cuadre):")
        for row in report.missing_rows:
            lines.append(f"  - {row.detail}")
    if report.warnings:
        lines.append("ADVERTENCIAS:")
        for warning in report.warnings:
            lines.append(f"  - {warning}")
    if report.checkpoints and any(c.difference is not None for c in report.checkpoints):
        lines.append("SALDOS IMPRESOS EN EL LIBRO:")
        for comparison in report.checkpoints:
            if comparison.printed is None:
                continue
            marker = "ok" if comparison.difference is not None and abs(comparison.difference) < 0.005 else "??"
            lines.append(
                f"  p{comparison.page:<4} {comparison.kind:<10} impreso "
                f"{_money(comparison.printed):>16}  calculado {_money(comparison.computed):>16}  {marker}"
            )
    lines.append("-" * 78)
    lines.append(f"ESTADO: {STATUS_MARK.get(report.status, '')} {report.status}")
    lines.append("=" * 78)
    return "\n".join(lines)


def _write_json(path: Path, result: ParseResult, report: ReconciliationReport) -> None:
    payload = {
        "file": result.path,
        "sha256": result.file_hash,
        "bank": result.bank,
        "pages": result.pages,
        "cover": asdict(result.cover),
        "totals": {
            "cargo": report.total_cargo,
            "abono": report.total_abono,
            "igtf": report.total_igtf,
            "net": report.computed_net,
        },
        "reconciliation": {
            "status": report.status,
            "differences": [asdict(d) for d in report.differences],
            "missing_rows": [asdict(d) for d in report.missing_rows],
            "warnings": report.warnings,
            "checkpoints": [asdict(c) for c in report.checkpoints],
        },
        "operations": [asdict(op) for op in result.operations],
        "annex": [asdict(op) for op in result.annex],
        "pos": [asdict(op) for op in result.pos],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, result: ParseResult) -> None:
    fields = [
        "page",
        "seq",
        "date",
        "number",
        "description",
        "cargo",
        "abono",
        "igtf",
        "method",
        "counterpart",
        "counterpart_account",
        "counterpart_bank",
        "reference",
        "concept",
        "occurred_at",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for op in result.operations:
            writer.writerow({field: getattr(op, field) for field in fields})


def _expand_targets(targets: list[str]) -> list[Path]:
    paths: list[Path] = []
    for target in targets:
        candidate = Path(target)
        if candidate.is_dir():
            paths.extend(sorted(candidate.glob("*.pdf")))
        elif any(char in target for char in "*?["):
            paths.extend(Path(p) for p in glob.glob(target))
        else:
            paths.append(candidate)
    unique: dict[str, Path] = {}
    for path in paths:
        unique[str(path.resolve())] = path
    return sorted(unique.values(), key=lambda p: p.name)


def cmd_parse(args: argparse.Namespace) -> int:
    try:
        result = parse_file(args.pdf)
    except UnsupportedBankError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    report = reconcile(result)
    print(_report_text(result, report))
    if args.json:
        _write_json(Path(args.json), result, report)
        print(f"JSON escrito en {args.json}")
    if args.csv:
        _write_csv(Path(args.csv), result)
        print(f"CSV escrito en {args.csv}")
    return 0 if report.status != "DIFERENCIAS" else 1


def cmd_validate(args: argparse.Namespace) -> int:
    paths = _expand_targets(args.targets)
    if not paths:
        print("No se encontraron archivos.", file=sys.stderr)
        return 2
    header = f"{'archivo':<52} {'págs':>4} {'filas':>6} {'cargos':>15} {'abonos':>15}  estado"
    print(header)
    print("-" * len(header))
    counts = {"CUADRA": 0, "DIFERENCIAS": 0, "REVISAR": 0}
    failures = 0
    for path in paths:
        try:
            result = parse_file(path)
            report = reconcile(result)
        except Exception as error:  # noqa: BLE001
            print(f"{path.name:<52} ERROR: {error}")
            failures += 1
            continue
        counts[report.status] = counts.get(report.status, 0) + 1
        detail = ""
        if report.differences:
            deltas = [
                f"{d.kind}:{_money(d.parsed - d.expected)}"
                for d in report.differences
                if d.parsed is not None and d.expected is not None
            ]
            detail = " " + ", ".join(deltas)
        elif report.warnings:
            detail = f" ({len(report.warnings)} advertencias)"
        print(
            f"{path.name:<52} {result.pages:>4} {len(result.operations):>6} "
            f"{report.total_cargo:>15,.2f} {report.total_abono:>15,.2f}  "
            f"{report.status}{detail}"
        )
    print("-" * len(header))
    print(
        f"Total: {len(paths)} archivos | CUADRA {counts.get('CUADRA', 0)} | "
        f"DIFERENCIAS {counts.get('DIFERENCIAS', 0)} | REVISAR {counts.get('REVISAR', 0)} | "
        f"errores {failures}"
    )
    return 0 if failures == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="estados-de-cuenta", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse", help="Parsea un estado de cuenta y muestra el peritaje")
    parse_cmd.add_argument("pdf")
    parse_cmd.add_argument("--json", help="Escribe el resultado completo en JSON")
    parse_cmd.add_argument("--csv", help="Escribe los movimientos en CSV")
    parse_cmd.set_defaults(func=cmd_parse)

    validate_cmd = sub.add_parser("validate", help="Valida y concilia varios archivos")
    validate_cmd.add_argument("targets", nargs="+", help="Archivos, directorios o globs")
    validate_cmd.set_defaults(func=cmd_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
