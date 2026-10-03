from app.parsers.base import parse_file
from app.parsers.reconcile import reconcile
from tests.synth import make_statement


def test_estado_sintetico_cuadra(tmp_path):
    path = make_statement(tmp_path / "estado.pdf")
    result = parse_file(path)

    assert result.cover.holder == "PEREZ JUAN"
    assert result.cover.account_number == "1601234567"
    assert result.cover.period_start == "01-01-24"
    assert result.cover.period_end == "31-01-24"
    assert result.cover.saldo_inicio == 1000.0
    assert result.cover.saldo_final == 1700.0

    assert len(result.operations) == 4
    assert result.total_cargo == 1500.0
    assert result.total_abono == 2200.0

    first = result.operations[0]
    assert "CUENTA DE JUAN PEREZ" in first.description
    assert first.method == "transferencia_enviada"
    assert first.counterpart == "Juan Perez"
    assert first.counterpart_account == "1234"
    assert first.occurred_at == "02-01-24 10:00:00"

    assert len(result.annex) == 2
    assert len(result.pos) == 1
    assert result.pos[0].amount == 500.0

    report = reconcile(result)
    assert report.status == "CUADRA", report.warnings
    assert report.total_cargo == 1500.0
    assert report.total_abono == 2200.0


def test_estado_sintetico_detecta_fila_omitida(tmp_path):
    path = make_statement(tmp_path / "estado_omitido.pdf", missing_debit=123.45)
    result = parse_file(path)
    report = reconcile(result)

    assert report.status == "DIFERENCIAS"
    cargo_diff = next(d for d in report.differences if d.kind == "cargo")
    assert round(cargo_diff.parsed - cargo_diff.expected, 2) == -123.45
    assert len(report.missing_rows) == 1
    assert "123,45" in report.missing_rows[0].detail
