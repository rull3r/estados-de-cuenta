"""Categorización de operaciones."""

from __future__ import annotations

DEFAULT_CATEGORIES: dict[str, str] = {
    "transferencia_recibida": "Ingresos",
    "credito_inmediato": "Ingresos",
    "pago_movil": "Pagos móviles",
    "comision_pago_movil": "Comisiones",
    "comision_credito_inmediato": "Comisiones",
    "comision": "Comisiones",
    "transferencia_enviada": "Transferencias",
    "punto_de_venta": "Consumos con tarjeta",
    "tarjeta_debito": "Consumos con tarjeta",
    "pago_terceros": "Pagos a terceros",
    "pago_servicios": "Servicios",
    "mantenimiento": "Cargos bancarios",
    "emision_estado": "Cargos bancarios",
    "mensajeria": "Cargos bancarios",
    "impuesto": "Impuestos",
    "cheque": "Cheques",
    "otro": "Otros",
}


def categorizer(
    method: str, search_key: str, rules: list[tuple[str, str]]
) -> str:
    """Categoría por regla del usuario; si no, por método de pago."""
    for pattern, category in rules:
        if pattern and pattern in search_key:
            return category
    return DEFAULT_CATEGORIES.get(method, "Otros")
