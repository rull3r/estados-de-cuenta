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
    assert fields["counterpart_bank"] == "Banco De Venezuela"


def test_extrae_ordenada_por_banco_y_hora():
    desc = (
        "OPERACION DE CREDITO INMEDIATO - TRANSF. RECIDE LA CCE ORDENADA POR V18809833 "
        "RIVERO FUENTES KATHERINE DEL CARMEN CUENTA 1340339203393172649 DE BANESCO "
        "BANCO UNIVERSAL, POR CONCEPTO DE: pep EL 02-01-26 A LAS 21:08:55 HORAS"
    )
    fields = enrich_operation(desc, direction="abono")
    assert fields["method"] == "credito_inmediato"
    assert fields["counterpart"] == "Rivero Fuentes Katherine Del Carmen"
    assert fields["counterpart_account"] == "1340339203393172649"
    assert fields["counterpart_bank"] == "Banesco Banco Universal"
    assert fields["concept"] == "pep"
    assert fields["occurred_at"] == "02-01-26 21:08:55"


def test_nombre_placeholder_se_descarta():
    desc = (
        "OPERACION DE CREDITO INMEDIATO - TRANSF. PRES A LA CCE A TRAVES DE MELP "
        "A/N DE V8169497 NOMBRE-BENEFICIARIO-TPG A LA CUENTA 1140370113701155024 "
        "EN BANCO DEL CARIBE C.A., BA POR CONCEPTO DE: pago"
    )
    fields = enrich_operation(desc, direction="cargo")
    assert fields["counterpart"] is None
    assert fields["counterpart_account"] == "1140370113701155024"
    assert fields["counterpart_bank"] == "Banco Del Caribe"


def test_formato_2023_y_direccion_decide_transferencia():
    desc = (
        "TRANFERENCIAS N/A TRANSFERENCIA POR INTERNET DESDE LA CUENTA NUMERO 001070443719 "
        "A LA CUENTA NUMERO 001619067307 POR Bs 700,00 POR CONCEPTO DE SKSN "
        "EL 05-08-23 A LAS 23:50:10 HORAS"
    )
    recibida = enrich_operation(desc, direction="abono")
    assert recibida["method"] == "transferencia_recibida"
    assert recibida["counterpart_account"] == "001070443719"
    assert recibida["concept"] == "SKSN"

    enviada = enrich_operation(desc, direction="cargo")
    assert enviada["method"] == "transferencia_enviada"
    assert enviada["counterpart_account"] == "001619067307"


def test_pago_2023_con_nombre_y_factura():
    desc = (
        "TRANFERENCIAS N/A PAGO POR INTERNET DE MISMOBANCO DESDE LA CUENTA NUMERO "
        "001619067307 A BORGES SANCHEZ ADRIANA SOLIVER POR LA CANTIDAD DE Bs640.00 "
        "POR ELCONCEPTO DE Adrian EL 03-08-23 A LAS 10:00:00 HORAS"
    )
    fields = enrich_operation(desc, direction="cargo")
    assert fields["method"] == "pago_terceros"
    assert fields["counterpart"] == "Borges Sanchez Adriana Soliver"
    assert fields["concept"] == "Adrian"


def test_envio_de_pago_extrae_nombre():
    desc = (
        "RECEPCION DE PAGO EL 06/04/2026 A LAS 10:58:35AM ENVIADO POR JESUS DIAZ "
        "DESDE EL 0424-6530036, CON REFERENCIA 048316639744 POR CONCEPTO DE pago. "
        "EL 06-04-26 A LAS 10:58:35 HORAS"
    )
    fields = enrich_operation(desc, direction="abono")
    assert fields["method"] == "pago_movil"
    assert fields["counterpart"] == "Jesus Diaz"
    assert fields["phone"] == "424-6530036"
    assert fields["reference"] == "048316639744"
