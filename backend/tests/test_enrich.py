from app.parsers.enrich import classify_method, enrich_operation, normalize_text
from app.parsers.linegrid import is_amount, parse_amount


def test_parse_amount_venezolano():
    assert parse_amount("1.234.567,89") == 1234567.89
    assert parse_amount("0,10") == 0.10
    assert parse_amount("30,19") == 30.19


def test_is_amount():
    assert is_amount("1.000,00")
    assert is_amount("-1.000,00")
    assert not is_amount("1,000.00")
    assert not is_amount("12/01")
    assert not is_amount("***7307")


def test_normalize_text_ignora_cortes_y_acentos():
    assert normalize_text("A LA CU ENT A") == normalize_text("a la cuenta")
    assert normalize_text("TRANSFERENCIA RECIBIDA") == "transferenciarecibida"
    assert normalize_text("José Ángel") == "joseangel"


def test_classify_method():
    assert classify_method("COMISION PAGO MOVIL INTERBANCARIO") == "comision_pago_movil"
    assert classify_method("TRANSFERENCIA DESDE LA CUENTA ***7307") == "transferencia_enviada"
    assert classify_method("TRANSFERENCIA RECIBIDA DESDE LA CUENTA ***391") == "transferencia_recibida"
    assert classify_method("PAGO MOVIL A UN MOVIL VIA APP") == "pago_movil"
    assert classify_method("CONSUMO PUNTO DE VENTA BIOPAGO") == "punto_de_venta"
    assert classify_method("PAGO A TERCEROS VIA INTERNET") == "pago_terceros"
    assert classify_method("OPERACION DE CREDITO INMEDIATO - TRANSF. PRES") == "credito_inmediato"
    assert classify_method("ALGO DESCONOCIDO") == "otro"


def test_enrich_operation_contraparte_y_referencias():
    desc = (
        "TRANSFERENCIA DESDE LA CUENTA ***7307 A LA CUENTA DE MARIA LARREAL ***2806 "
        "POR BS. 12,000.00 REALIZADA EN MERCANTIL EN LINEA PERSONAS EL 02/01/2026 "
        "A LAS 22:32 PM POR CONCEPTO DE pago EL 02-01-26 A LAS 22:32:33 HORAS"
    )
    fields = enrich_operation(desc)
    assert fields["method"] == "transferencia_enviada"
    assert fields["counterpart"] == "Maria Larreal"
    assert fields["counterpart_account"] == "2806"
    assert fields["occurred_at"] == "02-01-26 22:32:33"
    assert fields["concept"] is not None


def test_enrich_operation_pago_movil():
    desc = (
        "PAGO MOVIL A UN MOVIL VIA APP ENVIADO EL 28/07/2026 A LAS 03:49:45PM, "
        "AL 0414-4201827 EN BANCO DE VENEZUELA S, CON REFERENCIA 084730293391 "
        "POR CONCEPTO DE . EL 28-07-26 A LAS 15:49:45 HORAS"
    )
    fields = enrich_operation(desc)
    assert fields["method"] == "pago_movil"
    assert fields["reference"] == "084730293391"
    assert fields["phone"] == "414-4201827"
    assert fields["counterpart_bank"] is not None
