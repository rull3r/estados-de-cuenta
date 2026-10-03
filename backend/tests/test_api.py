import fitz
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from tests.synth import make_statement

client = TestClient(app)


def _pdf_en_blanco() -> bytes:
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    data = doc.tobytes()
    doc.close()
    return data


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.skipif(not config.FRONTEND_DIST.exists(), reason="frontend no compilado")
def test_spa_servida_por_el_backend():
    response = client.get("/")
    assert response.status_code == 200
    assert "estados de cuenta" in response.text.lower()


def test_flujo_completo_subida_parseo_y_estadisticas(tmp_path):
    path = make_statement(tmp_path / "estado_api.pdf")
    with path.open("rb") as handle:
        response = client.post(
            "/api/statements",
            files={"file": ("estado_api.pdf", handle, "application/pdf")},
        )
    assert response.status_code == 201, response.text
    statement_id = response.json()["id"]

    # TestClient ejecuta las tareas de fondo al terminar la respuesta
    detail = client.get(f"/api/statements/{statement_id}").json()
    assert detail["status"] == "CUADRA", detail
    assert detail["transaction_count"] == 4
    assert detail["report"]["month_name"] == "Enero"

    operations = client.get("/api/operations", params={"statement_id": statement_id}).json()
    assert operations["total"] == 4
    first = operations["items"][0]
    assert first["method"] == "transferencia_enviada"
    assert first["counterpart"] == "Juan Perez"
    assert first["category"] == "Transferencias"

    search = client.get("/api/operations", params={"text": "juan perez"}).json()
    assert search["total"] == 1

    summary = client.get("/api/stats/summary").json()
    assert summary["total_cargo"] == 1500.0
    assert summary["total_abono"] == 2200.0
    assert summary["count"] == 4
    assert summary["monthly"][0]["status"] == "CUADRA"

    export = client.get("/api/export.csv")
    assert export.status_code == 200
    assert "descripcion" in export.text


def test_subida_duplicada_devuelve_409(tmp_path):
    path = make_statement(tmp_path / "duplicado.pdf")
    with path.open("rb") as handle:
        first = client.post(
            "/api/statements", files={"file": ("duplicado.pdf", handle, "application/pdf")}
        )
    assert first.status_code == 201
    with path.open("rb") as handle:
        second = client.post(
            "/api/statements", files={"file": ("duplicado.pdf", handle, "application/pdf")}
        )
    assert second.status_code == 409


def test_ajustes_manuales(tmp_path):
    path = make_statement(tmp_path / "ajuste.pdf")
    with path.open("rb") as handle:
        response = client.post("/api/statements", files={"file": ("ajuste.pdf", handle, "application/pdf")})
    statement_id = response.json()["id"]
    created = client.post(
        f"/api/statements/{statement_id}/adjustments",
        json={
            "date": "31/01/24",
            "description": "Operación no impresa por el banco",
            "amount": 123.45,
            "direction": "cargo",
        },
    )
    assert created.status_code == 201
    detail = client.get(f"/api/statements/{statement_id}").json()
    assert len(detail["adjustments"]) == 1
    summary = client.get("/api/stats/summary").json()
    assert summary["adjustments"]["cargo"] == 123.45


def test_rechaza_archivo_que_no_es_pdf():
    response = client.post(
        "/api/statements",
        files={"file": ("notas.pdf", b"esto no es un pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_rechaza_pdf_que_no_es_estado_de_cuenta():
    response = client.post(
        "/api/statements",
        files={"file": ("otro.pdf", _pdf_en_blanco(), "application/pdf")},
    )
    assert response.status_code == 422
    assert "Mercantil" in response.json()["detail"]


def test_detecta_operaciones_repetidas_entre_estados(tmp_path):
    first = make_statement(tmp_path / "periodo_a.pdf")
    second = make_statement(tmp_path / "periodo_b.pdf", missing_debit=1.0)
    for path in (first, second):
        with path.open("rb") as handle:
            response = client.post(
                "/api/statements",
                files={"file": (path.name, handle, "application/pdf")},
            )
        assert response.status_code == 201
    second_id = response.json()["id"]

    duplicates = client.get("/api/stats/duplicates").json()
    assert duplicates, "debería detectar operaciones presentes en dos estados"
    group = duplicates[0]
    assert group["statement_count"] >= 2
    assert len(group["operations"]) >= 2
    assert all("statement_file" in operation for operation in group["operations"])

    detail = client.get(f"/api/statements/{second_id}").json()
    warnings = [issue for issue in detail["issues"] if issue["kind"] == "advertencia"]
    assert any("solapa" in issue["detail"] for issue in warnings)
