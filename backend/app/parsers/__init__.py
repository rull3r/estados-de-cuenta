"""Motores de parseo de estados de cuenta.

La arquitectura separa:

- ``model``: estructuras de datos neutrales al banco.
- ``linegrid``: lectura por coordenadas compartida por todos los bancos.
- ``enrich``: extracción de campos desde descripciones (método, contraparte, etc.).
- ``reconcile``: conciliación contra el resumen oficial del banco.
- ``mercantil``: adapter del banco Mercantil (Cuenta Corriente).

Para agregar un banco nuevo se implementa un adapter que consuma ``linegrid`` y
produzca un ``ParseResult``. Ver ``base.BankAdapter``.
"""

from .model import (  # noqa: F401
    AnnexOperation,
    Checkpoint,
    CoverSummary,
    Operation,
    ParseResult,
    PosOperation,
)
