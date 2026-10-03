"""Configuración de la aplicación."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("EDC_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = Path(os.environ.get("EDC_DB_PATH", DATA_DIR / "estados.db"))
FRONTEND_DIST = Path(os.environ.get("EDC_FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))

MAX_UPLOAD_MB = int(os.environ.get("EDC_MAX_UPLOAD_MB", "100"))

ALLOWED_BANKS = [
    {"id": "mercantil-corriente", "name": "Mercantil — Cuenta Corriente", "status": "activo"},
    {"id": "banesco", "name": "Banesco", "status": "proximamente"},
    {"id": "bdv", "name": "Banco de Venezuela", "status": "proximamente"},
    {"id": "bnc", "name": "BNC", "status": "proximamente"},
]


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
