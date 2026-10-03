"""Interfaz común para adapters de bancos."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

import fitz

from .model import ParseResult

# Los PDF de algunos bancos traen perfiles ICC dañados; PyMuPDF avisa por stderr.
try:  # pragma: no cover - depende de la versión de PyMuPDF
    fitz.TOOLS.mupdf_display_errors(False)
except Exception:  # noqa: BLE001
    pass


class BankAdapter(Protocol):
    """Contrato que implementa cada banco."""

    name: str
    display_name: str

    def detect(self, doc: fitz.Document) -> bool: ...

    def parse(self, path: str | Path) -> ParseResult: ...


class UnsupportedBankError(RuntimeError):
    pass


def file_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_adapters() -> list[BankAdapter]:
    from .mercantil import MercantilCorrienteAdapter

    return [MercantilCorrienteAdapter()]


def parse_file(path: str | Path) -> ParseResult:
    """Detecta el banco y parsea el estado de cuenta."""
    path = Path(path)
    with fitz.open(path) as doc:
        for adapter in get_adapters():
            if adapter.detect(doc):
                return adapter.parse(path)
    raise UnsupportedBankError(
        f"No se reconoce el banco/ formato del archivo: {path.name}. "
        "Por ahora solo está soportado Mercantil Cuenta Corriente."
    )
