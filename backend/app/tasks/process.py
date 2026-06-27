"""Celery задачи: обработка документа в воркере (раздел 4.1)."""

from __future__ import annotations

import uuid

from app.celery_app import celery
from app.database import SessionLocal
from app.services.document_service import process_document


@celery.task(name="app.tasks.process.process_document_task", bind=True, max_retries=2)
def process_document_task(self, doc_id: str) -> dict:
    db = SessionLocal()
    try:
        doc = process_document(db, uuid.UUID(doc_id))
        return {
            "doc_id": str(doc.doc_id),
            "status": doc.parse_status.value,
            "items": doc.item_count,
            "ocr": doc.ocr_applied,
        }
    finally:
        db.close()
