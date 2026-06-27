"""Загрузка ZIP/файлов: распаковка, регистрация, постановка в очередь (раздел 4.3)."""

from __future__ import annotations

import os
import tempfile
import zipfile

from sqlalchemy.orm import Session

from app.models import PriceDocument
from app.services.document_service import register_document

SUPPORTED_EXT = {".pdf", ".docx", ".xlsx", ".xls"}


def _is_supported(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in SUPPORTED_EXT


def ingest_paths(
    db: Session, paths: list[tuple[str, str]], enqueue: bool = True
) -> tuple[list[PriceDocument], list[str]]:
    """paths: список (local_path, original_name). Возвращает (документы, дубликаты)."""
    docs: list[PriceDocument] = []
    skipped: list[str] = []
    for local_path, name in paths:
        if not _is_supported(name):
            continue
        doc = register_document(db, local_path, file_name=name)
        if doc is None:
            skipped.append(name)
            continue
        docs.append(doc)

    if enqueue:
        from app.tasks.process import process_document_task

        for doc in docs:
            process_document_task.delay(str(doc.doc_id))
    return docs, skipped


def ingest_zip(
    db: Session, zip_path: str, enqueue: bool = True
) -> tuple[list[PriceDocument], list[str]]:
    paths: list[tuple[str, str]] = []
    tmp = tempfile.mkdtemp(prefix="medp_zip_")
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir() or not _is_supported(info.filename):
                continue
            # Имя без кириллических проблем кодировки cp437.
            try:
                name = info.filename.encode("cp437").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                name = info.filename
            base = os.path.basename(name)
            target = os.path.join(tmp, base)
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            paths.append((target, base))
    return ingest_paths(db, paths, enqueue=enqueue)
