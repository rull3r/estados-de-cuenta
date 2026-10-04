"""Endpoints de estados de cuenta: subida, listado, detalle y ajustes."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import fitz
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_session
from ..models import Adjustment, Statement
from ..parsers.base import get_adapters
from ..schemas import AdjustmentIn
from ..services.importer import process_statement, statement_to_dict

router = APIRouter(prefix="/api/statements", tags=["statements"])

# Si un estado lleva más de este tiempo «procesando», se considera interrumpido.
STALE_AFTER = timedelta(minutes=30)


def _public_statement(session: Session, statement_id: int) -> Statement:
    statement = session.get(Statement, statement_id)
    if statement is None:
        raise HTTPException(status_code=404, detail="Estado de cuenta no encontrado")
    return statement


def _is_stale(statement: Statement) -> bool:
    return statement.status == "procesando" and datetime.utcnow() - statement.uploaded_at > STALE_AFTER


def _requeue(session: Session, statement: Statement, file_name: str, path: Path, content: bytes) -> dict:
    path.write_bytes(content)
    statement.status = "procesando"
    statement.error = None
    statement.file_name = file_name
    statement.source_path = str(path)
    statement.uploaded_at = datetime.utcnow()
    session.commit()
    return statement_to_dict(statement)


@router.post("", status_code=201)
def upload_statement(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    file_name = Path(file.filename or "estado.pdf").name
    if not file_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    content = file.file.read()
    if len(content) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"El archivo supera {config.MAX_UPLOAD_MB} MB")

    # Validación temprana: que sea un PDF y que el banco sea reconocido.
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="El archivo no es un PDF válido")
    try:
        with fitz.open(stream=content, filetype="pdf") as probe:
            if probe.needs_pass:
                raise HTTPException(status_code=400, detail="El PDF está protegido con contraseña")
            recognized = any(adapter.detect(probe) for adapter in get_adapters())
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"No se pudo abrir el PDF: {error}") from error
    if not recognized:
        raise HTTPException(
            status_code=422,
            detail=(
                "El PDF no parece un estado de cuenta soportado. "
                "Por ahora se aceptan estados de cuenta de Mercantil (Cuenta Corriente)."
            ),
        )

    digest = hashlib.sha256(content).hexdigest()
    config.ensure_dirs()
    path = config.UPLOAD_DIR / f"{digest}.pdf"

    existing = session.scalar(select(Statement).where(Statement.file_hash == digest))
    if existing is not None:
        # Reintento si el intento anterior falló o si quedó atascado tras un reinicio.
        if existing.status == "error" or _is_stale(existing):
            payload = _requeue(session, existing, file_name, path, content)
            background.add_task(process_statement, existing.id, str(path))
            return payload
        if existing.status == "procesando":
            # Ya está en la cola del servidor: la web lo sigue con este mismo id.
            return statement_to_dict(existing)
        raise HTTPException(
            status_code=409,
            detail={"message": "Este archivo ya fue cargado", "statement_id": existing.id},
        )

    path.write_bytes(content)

    statement = Statement(
        bank="Mercantil — Cuenta Corriente",
        file_name=file_name,
        file_hash=digest,
        status="procesando",
        source_path=str(path),
    )
    session.add(statement)
    session.commit()
    session.refresh(statement)

    background.add_task(process_statement, statement.id, str(path))
    return statement_to_dict(statement)


@router.get("")
def list_statements(session: Session = Depends(get_session)) -> list[dict]:
    statements = session.scalars(
        select(Statement).order_by(Statement.period_start.desc(), Statement.id.desc())
    ).all()
    return [statement_to_dict(statement) for statement in statements]


@router.get("/{statement_id}")
def get_statement(statement_id: int, session: Session = Depends(get_session)) -> dict:
    return statement_to_dict(_public_statement(session, statement_id), detail=True)


@router.delete("/{statement_id}", status_code=204)
def delete_statement(statement_id: int, session: Session = Depends(get_session)) -> None:
    statement = _public_statement(session, statement_id)
    if statement.source_path:
        Path(statement.source_path).unlink(missing_ok=True)
    session.delete(statement)
    session.commit()


@router.post("/{statement_id}/adjustments", status_code=201)
def add_adjustment(
    statement_id: int,
    payload: AdjustmentIn,
    session: Session = Depends(get_session),
) -> dict:
    _public_statement(session, statement_id)
    adjustment = Adjustment(
        statement_id=statement_id,
        date=payload.date,
        description=payload.description,
        amount=payload.amount,
        direction=payload.direction,
        note=payload.note,
    )
    session.add(adjustment)
    session.commit()
    session.refresh(adjustment)
    return {
        "id": adjustment.id,
        "date": adjustment.date,
        "description": adjustment.description,
        "amount": adjustment.amount,
        "direction": adjustment.direction,
        "note": adjustment.note,
    }


@router.delete("/{statement_id}/adjustments/{adjustment_id}", status_code=204)
def delete_adjustment(
    statement_id: int,
    adjustment_id: int,
    session: Session = Depends(get_session),
) -> None:
    adjustment = session.get(Adjustment, adjustment_id)
    if adjustment is None or adjustment.statement_id != statement_id:
        raise HTTPException(status_code=404, detail="Ajuste no encontrado")
    session.delete(adjustment)
    session.commit()


@router.get("/{statement_id}/report")
def get_report(statement_id: int, session: Session = Depends(get_session)) -> dict:
    statement = _public_statement(session, statement_id)
    return json.loads(statement.report_json) if statement.report_json else {}


@router.post("/{statement_id}/reprocess")
def reprocess_statement(
    statement_id: int,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict:
    """Vuelve a leer el PDF original (útil tras mejorar el motor de extracción)."""
    statement = _public_statement(session, statement_id)
    if not statement.source_path or not Path(statement.source_path).exists():
        raise HTTPException(
            status_code=409,
            detail="No se encontró el PDF original en el servidor; vuelve a subirlo.",
        )
    if statement.status == "procesando":
        return statement_to_dict(statement)
    statement.status = "procesando"
    statement.error = None
    session.commit()
    background.add_task(process_statement, statement.id, statement.source_path)
    return statement_to_dict(statement)
