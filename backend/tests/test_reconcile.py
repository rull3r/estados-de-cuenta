from app.parsers.model import Checkpoint, CoverSummary, Operation, ParseResult
from app.parsers.reconcile import reconcile


def _result() -> ParseResult:
    result = ParseResult(
        path="sintetico.pdf",
        file_hash="x",
        bank="test",
        pages=2,
        cover=CoverSummary(
            saldo_inicio=100.0,
            depositos=0.0,
            otros_creditos=200.0,
            cheques=0.0,
            otros_debitos=150.0,
            igtf=0.0,
            saldo_final=150.0,
        ),
    )
    abono = Operation(page=1, seq=1, date="02/01", number="1", description="", cargo=0.0, abono=200.0, igtf=0.0)
    abono.balance_computed = 300.0
    cargo = Operation(page=1, seq=2, date="03/01", number="2", description="", cargo=150.0, abono=0.0, igtf=0.0)
    cargo.balance_computed = 150.0
    result.operations = [abono, cargo]
    result.checkpoints = [
        Checkpoint(page=1, kind="inicio", label="inicio", printed_balance=100.0, computed_balance=100.0),
        Checkpoint(
            page=1,
            kind="intermedio",
            label="fila con saldo",
            printed_balance=150.0,
            op_index=1,
            computed_balance=150.0,
        ),
        Checkpoint(page=1, kind="final", label="final", printed_balance=150.0, computed_balance=150.0),
    ]
    return result


def test_cuadra_al_centimo():
    report = reconcile(_result())
    assert report.status == "CUADRA"
    assert report.differences == []
    assert report.missing_rows == []


def test_detecta_fila_omitida_por_el_banco():
    result = _result()
    result.cover.otros_debitos = 180.0  # el resumen incluye 30 que el libro no imprime
    result.cover.saldo_final = 120.0
    result.checkpoints[1].printed_balance = 120.0
    result.checkpoints[2].printed_balance = 120.0
    report = reconcile(result)
    assert report.status == "DIFERENCIAS"
    assert any(d.kind == "cargo" for d in report.differences)
    assert len(report.missing_rows) == 1
    assert "30" in report.missing_rows[0].detail


def test_anexo_que_no_cruza_genera_advertencia():
    from app.parsers.model import AnnexOperation

    result = _result()
    result.annex = [
        AnnexOperation(page=2, date_tr="02/01", date_op="02/01", description="x", amount=999.0)
    ]
    report = reconcile(result)
    assert report.status == "REVISAR"
    assert any("anexo" in w.lower() for w in report.warnings)
