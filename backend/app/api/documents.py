"""Загрузка архива и статус обработки документов (раздел 10)."""

from __future__ import annotations

import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PriceDocument
from app.schemas import (
    DocumentOut,
    DocumentStatusOut,
    UploadResponse,
)
from app.services.upload_service import ingest_paths, ingest_zip

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    enqueue: bool = Query(True, description="Поставить в очередь Celery"),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Загрузка ZIP архива или одиночного прайса. Запускает pipeline."""
    suffix = os.path.splitext(file.filename or "upload")[1].lower()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await file.read())
        tmp.flush()
        tmp.close()
        if suffix == ".zip":
            docs, skipped = ingest_zip(db, tmp.name, enqueue=enqueue)
        else:
            docs, skipped = ingest_paths(db, [(tmp.name, file.filename)], enqueue=enqueue)
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)

    return UploadResponse(
        documents=[DocumentOut.model_validate(d) for d in docs],
        skipped_duplicates=skipped,
        message=f"Принято документов: {len(docs)}, дубликатов пропущено: {len(skipped)}",
    )


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    stmt = select(PriceDocument).order_by(PriceDocument.created_at.desc())
    if status:
        stmt = stmt.where(PriceDocument.parse_status == status)
    rows = db.execute(stmt).scalars().all()
    return [DocumentOut.model_validate(d) for d in rows]


@router.get("/documents/{doc_id}/status", response_model=DocumentStatusOut)
def document_status(doc_id: uuid.UUID, db: Session = Depends(get_db)) -> DocumentStatusOut:
    doc = db.get(PriceDocument, doc_id)
    if doc is None:
        raise HTTPException(404, "Документ не найден")
    return DocumentStatusOut(
        doc_id=doc.doc_id,
        file_name=doc.file_name,
        parse_status=doc.parse_status.value,
        item_count=doc.item_count,
        ocr_applied=doc.ocr_applied,
        processing_seconds=doc.processing_seconds,
        parse_log=doc.parse_log,
    )
