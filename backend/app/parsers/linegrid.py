"""Lectura por coordenadas: convierte páginas PDF en líneas lógicas.

Los estados de cuenta de Mercantil (y de otros bancos locales) se generan como
reportes de ancho fijo: cada página física contiene dos tablas lado a lado y el
texto de una descripción puede partirse a mitad de palabra. Este módulo expone
las primitivas para reconstruir esas líneas y clasificar montos por columna.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import fitz

AMOUNT_RE = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$")
DATE_RE = re.compile(r"^\d{2}/\d{2}$")
DAY_RE = re.compile(r"^\d{2}$")
DOTTED_DATE_RE = re.compile(r"^\d{2}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


@dataclass(frozen=True)
class Token:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    @property
    def x2(self) -> float:
        return self.x1


@dataclass
class Line:
    page: int
    side: str  # "L" | "R"
    y: float
    tokens: list[Token] = field(default_factory=list)
    side_x0: float = 0.0

    @property
    def text(self) -> str:
        return " ".join(t.text for t in self.tokens)

    @property
    def words(self) -> list[str]:
        return [t.text for t in self.tokens]


def is_amount(text: str) -> bool:
    return bool(AMOUNT_RE.match(text))


def parse_amount(text: str) -> float:
    """Convierte ``1.234.567,89`` a ``1234567.89``."""
    return float(text.replace(".", "").replace(",", "."))


def detect_split(words: list[tuple], width: float) -> float:
    """Encuentra la x donde parte la página en dos tablas.

    Busca el hueco horizontal más grande en la zona central. Si no hay hueco
    (documento de una sola columna), devuelve ``width + 1`` para forzar una
    única columna lógica.
    """
    xs = sorted(w[0] for w in words)
    if len(xs) < 2:
        return width + 1
    lo, hi = width * 0.25, width * 0.75
    best_gap, best_at = 0.0, None
    for a, b in zip(xs, xs[1:], strict=False):
        if a < lo or b > hi:
            continue
        gap = b - a
        if gap > best_gap:
            best_gap, best_at = gap, (a + b) / 2
    if best_gap >= 22 and best_at is not None:
        return best_at
    return width / 2 if width > 640 else width + 1


def cluster_lines(
    words: list[tuple],
    page: int,
    side: str,
    side_x0: float = 0.0,
    tolerance: float = 3.5,
) -> list[Line]:
    """Agrupa palabras en líneas visuales por cercanía vertical."""
    tokens = [
        Token(x0=float(w[0]), y0=float(w[1]), x1=float(w[2]), y1=float(w[3]), text=w[4])
        for w in words
    ]
    tokens.sort(key=lambda t: (t.y0, t.x0))
    lines: list[Line] = []
    current: list[Token] = []
    baseline = 0.0
    for token in tokens:
        if not current:
            current = [token]
            baseline = token.y0
            continue
        if abs(token.y0 - baseline) <= tolerance:
            current.append(token)
        else:
            lines.append(
                Line(page, side, baseline, sorted(current, key=lambda t: t.x0), side_x0)
            )
            current = [token]
            baseline = token.y0
    if current:
        lines.append(Line(page, side, baseline, sorted(current, key=lambda t: t.x0), side_x0))
    return lines


def page_lines(page: fitz.Page, page_no: int) -> list[Line]:
    """Extrae las líneas lógicas de una página, en orden de lectura.

    El orden de lectura real de estos reportes es: columna izquierda completa,
    luego columna derecha.
    """
    words = page.get_text("words")
    if not words:
        return []
    split = detect_split(words, page.rect.width)
    out: list[Line] = []
    for side, (xa, xb) in (("L", (0.0, split)), ("R", (split, page.rect.width + 1))):
        ws = [w for w in words if xa <= w[0] < xb]
        if not ws:
            continue
        out.extend(cluster_lines(ws, page_no, side, 0.0 if side == "L" else split))
    return out


def page_lines_raw(page: fitz.Page, page_no: int) -> list[Line]:
    """Líneas de una página sin partir en columnas (para el resumen/portada)."""
    words = page.get_text("words")
    if not words:
        return []
    return cluster_lines(words, page_no, "L", 0.0)


def find_column_anchors(line: Line) -> dict[str, float]:
    """Dado el renglón de encabezados, devuelve el borde derecho de cada columna.

    Los montos se imprimen alineados a la derecha contra el borde derecho del
    encabezado de su columna (+2pt de tolerancia).
    """
    anchors: dict[str, float] = {}
    wanted = ("CARGOS", "ABONOS", "SALDO", "IMPUESTO", "MONTO")
    for token in line.tokens:
        if token.text in wanted:
            anchors[token.text] = token.x2 + 2.0
    return anchors


def amount_anchor_from_tokens(tokens: list[Token]) -> float | None:
    """Fallback: infiere la columna de montos como el cúmulo más a la derecha."""
    xs = [round(t.x2 / 4) * 4 for t in tokens if is_amount(t.text)]
    if not xs:
        return None
    counts: dict[int, int] = {}
    for x in xs:
        counts[x] = counts.get(x, 0) + 1
    return float(max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0])


def classify_amount(x2: float, anchors: dict[str, float], tolerance: float = 16.0) -> str | None:
    """Asigna un monto a la columna cuyo borde derecho esté más cerca."""
    best: str | None = None
    best_distance = tolerance
    for name, anchor in anchors.items():
        distance = abs(x2 - anchor)
        if distance < best_distance:
            best, best_distance = name, distance
    return best
