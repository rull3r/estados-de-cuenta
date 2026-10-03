"""Asegura que el paquete ``app`` sea importable al correr pytest desde backend/.

Además aísla la base de datos de las pruebas en un directorio temporal para no
tocar los datos reales del usuario.
"""

import os
import sys
import tempfile
from pathlib import Path

_TEST_DIR = Path(tempfile.mkdtemp(prefix="edc-test-"))
os.environ.setdefault("EDC_DATA_DIR", str(_TEST_DIR / "data"))
os.environ.setdefault("EDC_DB_PATH", str(_TEST_DIR / "test.db"))

sys.path.insert(0, str(Path(__file__).parent))
