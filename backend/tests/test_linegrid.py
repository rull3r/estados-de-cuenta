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
