"""Оркестрация обработки одного документа (раздел 4.3).

Поток: формат -> экстрактор -> парсер цен -> валидация -> сохранение позиций
с происхождением -> нормализация (каскад) -> версионирование. Идемпотентно:
повторная обработка архивирует старые позиции и создаёт новые (раздел 4.4).
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import (
    FileFormat,
    ParseStatus,
    PriceDocument,
    PriceItem,
)
from app.normalization.cascade import MatchCascade
from app.normalization.match_service import apply_match
from app.pipeline.price_parser import expand_primary_repeat
from app.pipeline.registry import build_default_registry
from app.pipeline.router import classify_pdf, detect_format, parse_effective_date
from app.services.partner_service import resolve_partner
from app.storage import get_storage
from app.validation.checks import convert_to_kzt, validate_extracted
from app.validation.versioning import apply_versioning


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def register_document(db: Session, file_path: str, file_name: str | None = None) -> PriceDocument | None:
    """Регистрирует документ (без обработки). Возвращает None для дубликата по hash."""
    file_name = file_name or os.path.basename(file_path)
    fmt = detect_format(file_path)
    if fmt == FileFormat.pdf:
        fmt = classify_pdf(file_path)

    digest = file_sha256(file_path)
    existing = db.execute(
        select(PriceDocument).where(PriceDocument.file_hash == digest)
    ).scalar_one_or_none()
    if existing:
        return None

    partner = resolve_partner(db, file_name)
    storage = get_storage()
    key = f"{partner.partner_id}/{digest}_{file_name}"
    storage_path = storage.save(key, file_path)

    doc = PriceDocument(
        partner_id=partner.partner_id,
        file_name=file_name,
        file_format=fmt,
        file_hash=digest,
        storage_path=storage_path,
        effective_date=parse_effective_date(file_name),
        parse_status=ParseStatus.pending,
    )
    db.add(doc)
    db.commit()
    return doc


def process_document(db: Session, doc_id: uuid.UUID) -> PriceDocument:
    """Полная обработка документа. Вызывается из Celery задачи."""
    doc = db.get(PriceDocument, doc_id)
    if doc is None:
        raise LookupError(f"Документ {doc_id} не найден")

    started = time.monotonic()
    doc.parse_status = ParseStatus.processing
    db.commit()

    log: list[str] = []
    try:
        storage = get_storage()
        local_path = storage.open_path(doc.storage_path)

        registry = build_default_registry()
        extractor = registry.get_extractor(local_path, doc.file_format.value)
        result = extractor.extract(local_path)
        log.extend(result.warnings)

        doc.extractor_used = result.extractor_used or extractor.name
        doc.ocr_applied = result.ocr_applied
        doc.page_count = result.page_count
        doc.raw_content = (result.raw_content or "")[:1_000_000]

        # Архивируем прошлые позиции этого документа (идемпотентность, раздел 4.4).
        _archive_previous_items(db, doc.doc_id)

        effective = doc.effective_date or parse_effective_date(doc.file_name, result.raw_content)
        if effective and effective != doc.effective_date:
            doc.effective_date = effective

        saved_items: list[PriceItem] = []
        skipped = 0
        for raw_item in result.items:
            for parsed in expand_primary_repeat(raw_item):
                check = validate_extracted(parsed, effective)
                if not check.ok:
                    skipped += 1
                    continue
                parsed.price_resident_kzt = convert_to_kzt(
                    parsed.price_resident_kzt, parsed.currency_original
                )
                item = PriceItem(
                    doc_id=doc.doc_id,
                    partner_id=doc.partner_id,
                    service_name_raw=parsed.service_name_raw.strip()[:2000],
                    service_code_source=parsed.service_code_source,
                    price_resident_kzt=parsed.price_resident_kzt,
                    price_nonresident_kzt=parsed.price_nonresident_kzt,
                    price_original=parsed.price_original,
                    currency_original=parsed.currency_original,
                    effective_date=effective,
                    raw_price_label=parsed.raw_price_label,
                    category=parsed.category,
                    source_page=parsed.source_page,
                    source_row=parsed.source_row,
                    needs_review=check.needs_review,
                )
                db.add(item)
                saved_items.append(item)
        db.flush()

        if not saved_items:
            doc.parse_status = ParseStatus.error
            log.append("Документ без распознаваемых данных")
            doc.item_count = 0
            doc.parsed_at = datetime.now(UTC)
            doc.processing_seconds = time.monotonic() - started
            doc.parse_log = "\n".join(log)[:50_000]
            db.commit()
            return doc

        # Нормализация: один индекс на документ (раздел 8).
        cascade = MatchCascade(db)
        review_count = 0
        for item in saved_items:
            outcome = cascade.match(item.service_name_raw, item.category, item.service_code_source)
            apply_match(db, item, outcome)
            apply_versioning(db, item)
            if item.needs_review or item.service_id is None:
                review_count += 1

        doc.item_count = len(saved_items)
        doc.parse_status = (
            ParseStatus.needs_review if review_count else ParseStatus.done
        )
        if skipped:
            log.append(f"Пропущено пустых/битых строк: {skipped}")
        log.append(
            f"Извлечено {len(saved_items)} позиций, в ревью {review_count}, OCR={doc.ocr_applied}"
        )
        doc.parsed_at = datetime.now(UTC)
        doc.processing_seconds = time.monotonic() - started
        doc.parse_log = "\n".join(log)[:50_000]
        db.commit()
        return doc

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        doc = db.get(PriceDocument, doc_id)
        doc.parse_status = ParseStatus.error
        doc.parse_log = (("\n".join(log) + "\n") if log else "") + f"Ошибка обработки: {exc}"
        doc.processing_seconds = time.monotonic() - started
        doc.parsed_at = datetime.now(UTC)
        db.commit()
        return doc


def _archive_previous_items(db: Session, doc_id: uuid.UUID) -> None:
    """Помечает прошлые позиции документа архивными (не удаляет)."""
    db.execute(
        update(PriceItem)
        .where(PriceItem.doc_id == doc_id, PriceItem.is_active.is_(True))
        .values(is_active=False)
    )
    db.flush()
