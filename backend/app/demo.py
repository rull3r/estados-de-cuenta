"""Generador de estados de cuenta sintéticos para la demo y los tests.

No contiene datos reales: construye un PDF con la misma geometría que los
reportes de Mercantil (dos columnas, descripciones cortadas, anexos) para poder
probar el parser sin subir información personal.

Uso:
    python -m app.demo [ruta_salida.pdf] [--con-fila-omitida 123.45]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz

FONT = "helv"
SIZE = 7.0
DESC_SIZE = 5.0
SPLIT = 400.0

# Posiciones relativas dentro de cada columna del libro
DATE_X = 2.0
NUMBER_X = 28.0
DESC_X = 65.0
CARGOS_X = 185.0
ABONOS_X = 225.0
SALDO_X = 270.0
IMPUESTO_X = 310.0


def _text(page: fitz.Page, x: float, y: float, text: str, size: float = SIZE) -> None:
    page.insert_text((x, y), text, fontname=FONT, fontsize=size)


def _width(text: str, size: float = SIZE) -> float:
    return fitz.get_text_length(text, fontname=FONT, fontsize=size)


def _right(page: fitz.Page, x_right: float, y: float, text: str, size: float = SIZE) -> None:
    page.insert_text((x_right - _width(text, size), y), text, fontname=FONT, fontsize=size)


def _money(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cover(
    page: fitz.Page,
    *,
    saldo_inicio: float,
    creditos: float,
    debitos: float,
    saldo_final: float,
) -> None:
    _text(page, 130, 150, "PEREZ JUAN")
    _text(page, 130, 158, "CALLE FALSA 123, CARACAS")
    _text(page, 420, 225, "RESUMEN ESTADO DE CUENTA CORRIENTE")
    _text(page, 420, 270, "BANCO OFICINA D.C. NRO. DE CUENTA")
    _text(page, 420, 285, "0105 0619 11 1601234567")
    _text(page, 420, 300, "DESDE 01-01-24 HASTA 31-01-24")

    _text(page, 420, 320, "SALDO AL INICIO DEL PERIODO:")
    _right(page, 732, 320, _money(saldo_inicio))
    _text(page, 420, 338, "MAS: DEPOSITOS EFECTUADOS POR")
    _right(page, 732, 338, "0,00")
    _text(page, 420, 348, "OTROS CREDITOS A SU CUENTA")
    _right(page, 732, 348, _money(creditos))
    _text(page, 420, 378, "MENOS: CHEQUES DEBITADOS POR")
    _right(page, 732, 378, "0,00")
    _text(page, 420, 388, "OTROS DEBITOS A SU CUENTA")
    _right(page, 732, 388, _money(debitos))
    _text(page, 420, 408, "IMPUESTO AL IGTF")
    _right(page, 732, 408, "0,00")
    _text(page, 420, 428, "SALDO AL FINAL DEL PERIODO:")
    _right(page, 732, 428, _money(saldo_final))


def _column_anchors(origin: float) -> dict[str, float]:
    return {
        "CARGOS": origin + CARGOS_X + _width("CARGOS") + 1,
        "ABONOS": origin + ABONOS_X + _width("ABONOS") + 1,
        "SALDO": origin + SALDO_X + _width("SALDO") + 1,
        "IMPUESTO": origin + IMPUESTO_X + _width("IMPUESTO") + 1,
    }


def _column_header(page: fitz.Page, origin: float) -> None:
    _text(page, origin + 1, 71, "MOVIMIENTOS DE CUENTA")
    _text(page, origin + DATE_X, 88, "FECHA")
    _text(page, origin + NUMBER_X, 88, "NUMERO")
    _text(page, origin + DESC_X, 88, "DESCRIPCION")
    _text(page, origin + CARGOS_X, 88, "CARGOS")
    _text(page, origin + ABONOS_X, 88, "ABONOS")
    _text(page, origin + SALDO_X, 88, "SALDO")
    _text(page, origin + IMPUESTO_X, 88, "IMPUESTO")


def _ledger_row(
    page: fitz.Page,
    origin: float,
    y: float,
    *,
    date: str,
    number: str,
    desc_lines: list[str],
    cargo: float = 0.0,
    abono: float = 0.0,
    saldo: float | None = None,
) -> None:
    _text(page, origin + DATE_X, y, date)
    _text(page, origin + NUMBER_X, y, number)
    for index, line in enumerate(desc_lines):
        _text(page, origin + DESC_X, y + index * 7.5, line, size=DESC_SIZE)
    anchors = _column_anchors(origin)
    if cargo:
        _right(page, anchors["CARGOS"], y, _money(cargo))
    if abono:
        _right(page, anchors["ABONOS"], y, _money(abono))
    if saldo is not None:
        _right(page, anchors["SALDO"], y, _money(saldo))


def _annex_page(page: fitz.Page, operations: list[tuple[str, str, float]]) -> None:
    origin = 10.0
    _text(page, origin, 71, "MERCANTIL EN LINEA")
    _text(page, origin + DATE_X, 88, "FECHA")
    _text(page, origin + 28, 88, "TR.")
    _text(page, origin + 45, 88, "FECHA")
    _text(page, origin + 70, 88, "OPERACION")
    _text(page, origin + 250, 88, "MONTO")
    amount_right = origin + 250 + _width("MONTO") + 1
    y = 105.0
    for date_tr, description, amount in operations:
        _text(page, origin + DATE_X, y, date_tr)
        _text(page, origin + 28, y, date_tr)
        _text(page, origin + 60, y, description, size=DESC_SIZE)
        _right(page, amount_right, y, _money(amount))
        y += 7.5
        _text(page, origin + DATE_X, y, date_tr)
        _text(page, origin + 30, y, "EL 02-01-24 A LAS 10:00:00 HORAS")
        y += 9.0


def _pos_section(page: fitz.Page, y: float, rows: list[tuple[str, str, float]]) -> None:
    origin = 10.0
    _text(page, origin + 40, y, "PUNTOS DE VENTA")
    _text(page, origin + 40, y + 10, "TRANSACCION")
    _text(page, origin + 40, y + 19, "ESTABLECIMIENTO")
    _text(page, origin + 250, y + 19, "MONTO")
    amount_right = origin + 250 + _width("MONTO") + 1
    cursor = y + 30
    for date, description, amount in rows:
        _text(page, origin + 42, cursor, date)
        _text(page, origin + 65, cursor, description, size=DESC_SIZE)
        _right(page, amount_right, cursor, _money(amount))
        cursor += 7.5


def make_statement(path: str | Path, *, missing_debit: float | None = None) -> Path:
    """Genera un estado de cuenta sintético.

    Si ``missing_debit`` se indica, el resumen oficial y los saldos impresos
    incluyen un débito que el libro no imprime (simula el defecto real de
    Mercantil) para probar el detector de filas omitidas.
    """
    path = Path(path)
    doc = fitz.open()

    saldo_inicio = 1000.0
    abonos = 2000.0 + 200.0
    debitos_libro = 1000.0 + 500.0
    extra = missing_debit or 0.0
    saldo_final = saldo_inicio + abonos - debitos_libro - extra

    cover = doc.new_page(width=792, height=612)
    _cover(
        cover,
        saldo_inicio=saldo_inicio,
        creditos=abonos,
        debitos=debitos_libro + extra,
        saldo_final=saldo_final,
    )

    page = doc.new_page(width=792, height=612)
    _column_header(page, 10.0)
    _column_header(page, SPLIT)
    _text(page, 10 + DATE_X, 104, "01 01")
    _text(page, 10 + DESC_X, 104, "SALDO AL INICIO DEL PERIODO")
    _right(page, _column_anchors(10.0)["SALDO"], 104, _money(saldo_inicio))

    _ledger_row(
        page,
        10.0,
        122.0,
        date="02/01",
        number="00000001",
        desc_lines=[
            "TRANSFERENCIA DESDE LA CUENTA ***7307 A LA CU",
            "ENTA DE JUAN PEREZ ***1234 POR BS. 1,000.00",
            "REALIZADA EN MERCANTIL EN LINEA PERSONAS",
            "EL 02-01-24 A LAS 10:00:00 HORAS",
        ],
        cargo=1000.0,
    )
    _ledger_row(
        page,
        10.0,
        180.0,
        date="03/01",
        number="00000002",
        desc_lines=[
            "TRANSFERENCIA RECIBIDA DESDE LA",
            "CUENTA ***5566 POR BS. 2,000.00",
            "EL 03-01-24 A LAS 11:30:00 HORAS",
        ],
        abono=2000.0,
    )
    running_after_third = saldo_inicio - 1000.0 + 2000.0 - 500.0 - extra
    _ledger_row(
        page,
        10.0,
        220.0,
        date="04/01",
        number="00000003",
        desc_lines=[
            "PAGO A TERCEROS VIA INTERNET",
            "EL 04-01-24 A LAS 12:00:00 HORAS",
        ],
        cargo=500.0,
        saldo=running_after_third,
    )
    _ledger_row(
        page,
        SPLIT,
        122.0,
        date="05/01",
        number="00000004",
        desc_lines=[
            "TRANSFERENCIA RECIBIDA DESDE LA",
            "CUENTA ***7788 POR BS. 200.00",
            "EL 05-01-24 A LAS 09:00:00 HORAS",
        ],
        abono=200.0,
    )
    _text(page, SPLIT + DATE_X, 200, "31/01")
    _text(page, SPLIT + DESC_X, 200, "SALDO AL FINAL DEL PERIODO")
    _right(page, _column_anchors(SPLIT)["SALDO"], 200, _money(saldo_final))

    annex = doc.new_page(width=792, height=612)
    _text(annex, 500, 580, "Mercantil, C.A., Banco Universal, RIF. J-00002961-0")
    _annex_page(
        annex,
        [
            ("02/01", "TRANSFERENCIA DESDE LA CUENTA ***7307 A LA CU", 1000.0),
            ("03/01", "TRANSFERENCIA RECIBIDA DESDE LA CUENTA ***5566", 2000.0),
        ],
    )
    _pos_section(annex, 300.0, [("04/01", "CONSUMO TARJETA DE DEBITO", 500.0)])

    doc.save(path)
    doc.close()
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera un estado de cuenta sintético de demostración"
    )
    parser.add_argument(
        "output",
        nargs="?",
        default="demo/estado-sintetico-demo.pdf",
        help="Ruta del PDF a generar",
    )
    parser.add_argument(
        "--con-fila-omitida",
        type=float,
        default=None,
        help="Simula una fila que el banco no imprime (monto del débito)",
    )
    args = parser.parse_args(argv)
    target = make_statement(args.output, missing_debit=args.con_fila_omitida)
    print(f"Estado de cuenta sintético generado en: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
