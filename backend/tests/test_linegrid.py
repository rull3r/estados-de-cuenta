from app.parsers.linegrid import cluster_lines, detect_split
from app.parsers.mercantil import _join_parts


def _word(x0, y0, x1, y1, text):
    return (x0, y0, x1, y1, text, 0, 0, 0)


def test_detect_split_encuentra_hueco_central():
    words = [
        _word(10, 100, 40, 107, "izq"),
        _word(60, 100, 90, 107, "más"),
        _word(500, 100, 530, 107, "der"),
    ]
    split = detect_split(words, 792)
    assert 90 < split < 500


def test_cluster_lines_agrupa_por_y():
    words = [
        _word(10, 100.0, 40, 107, "A"),
        _word(45, 100.2, 70, 107, "B"),
        _word(10, 120.0, 40, 127, "C"),
    ]
    lines = cluster_lines(words, 1, "L")
    assert len(lines) == 2
    assert [t.text for t in lines[0].tokens] == ["A", "B"]
    assert [t.text for t in lines[1].tokens] == ["C"]


def test_join_parts_une_cortes_duros_sin_espacio():
    parts = [
        ("TRANSFERENCIA DESDE LA CU", True),
        ("ENTA DE JUAN PEREZ", False),
        ("POR BS. 1,000.00", False),
        ("REALIZADA", False),
    ]
    assert _join_parts(parts) == "TRANSFERENCIA DESDE LA CUENTA DE JUAN PEREZ POR BS. 1,000.00 REALIZADA"


def test_join_parts_repara_artefactos_sin_inventar():
    parts = [
        ("TRANSFERENCIA DESDE LA CUENTA ***7307 POR CONCEPTO DE P", True),
        ("EL 02-01-26 A LAS 22:32:33 HORAS", False),
    ]
    out = _join_parts(parts)
    assert "CONCEPTO DE P EL 02-01-26" in out

    parts2 = [
        ("REALIZADA EN MERCANTIL PERSONAS", True),
        ("EL 01/09/2024 A LAS15:07 PM POR CONCEPTO DE pago", False),
    ]
    out2 = _join_parts(parts2)
    assert "PERSONAS EL 01/09/2024" in out2
    assert "A LAS 15:07" in out2

    parts3 = [("OPERACION DE CREDITO INMEDIATO - TRANSF. RECI", True), ("DE LA CCE", False)]
    assert "TRANSF. RECI DE LA CCE" in _join_parts(parts3)
