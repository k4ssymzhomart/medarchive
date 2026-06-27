"""Применение каскада к позициям и ручное сопоставление (раздел 8.4, 9.4)."""

from __future__ import annotations

import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MatchMethod, PriceItem, Service, ServiceMatchCandidate
from app.normalization.cascade import MatchCascade, MatchOutcome
from app.normalization.lexical import LexicalIndex
from app.normalization.normalize import normalize


def _store_candidates(db: Session, item: PriceItem, outcome: MatchOutcome) -> None:
    db.execute(delete(ServiceMatchCandidate).where(ServiceMatchCandidate.item_id == item.item_id))
    for cand in outcome.candidates[:10]:
        db.add(
            ServiceMatchCandidate(
                item_id=item.item_id,
                service_id=cand.service_id,
                score=cand.score,
                method=cand.method,
                rank=cand.rank,
            )
        )


def apply_match(db: Session, item: PriceItem, outcome: MatchOutcome) -> None:
    """Записывает результат каскада в позицию и кандидатов."""
    item.match_confidence = outcome.score
    item.match_method = outcome.method
    if outcome.note:
        item.verification_note = outcome.note

    if outcome.service_id is not None and outcome.score >= settings.match_high_threshold:
        item.service_id = outcome.service_id
        item.needs_review = False
        item.is_verified = outcome.method in (MatchMethod.exact, MatchMethod.llm)
    elif outcome.service_id is not None:
        # пограничный авто-выбор (например, LLM) — в ревью для подтверждения
        item.service_id = outcome.service_id
        item.needs_review = True
    else:
        item.service_id = None
        item.needs_review = bool(outcome.candidates)  # есть кандидаты -> needs_review, иначе unmatched

    _store_candidates(db, item, outcome)
    db.flush()


def match_item(db: Session, item: PriceItem, cascade: MatchCascade | None = None) -> MatchOutcome:
    cascade = cascade or MatchCascade(db)
    outcome = cascade.match(item.service_name_raw, item.category, item.service_code_source)
    apply_match(db, item, outcome)
    return outcome


def learn_synonym(db: Session, service: Service, raw_name: str) -> bool:
    """Добавляет подтверждённое сырое название в синонимы услуги (раздел 8.4)."""
    raw_name = (raw_name or "").strip()
    if not raw_name:
        return False
    norm_raw = normalize(raw_name)
    if norm_raw == normalize(service.service_name):
        return False
    existing = {normalize(s) for s in (service.synonyms or [])}
    if norm_raw in existing:
        return False
    service.synonyms = [*(service.synonyms or []), raw_name]
    db.flush()
    return True


def manual_match(
    db: Session,
    item_id: uuid.UUID,
    service_id: uuid.UUID | None,
    action: str = "confirm",
    note: str | None = None,
) -> dict:
    """Ручное сопоставление оператором (POST /match). confirm | reject | correct."""
    item = db.get(PriceItem, item_id)
    if item is None:
        raise LookupError("Позиция не найдена")

    learned = 0
    if action == "reject":
        item.service_id = None
        item.match_method = MatchMethod.manual
        item.match_confidence = 0.0
        item.is_verified = True
        item.needs_review = False
        item.verification_note = note or "Оператор: совпадения нет"
    else:  # confirm | correct
        if service_id is None:
            raise ValueError("Для confirm/correct требуется service_id")
        service = db.get(Service, service_id)
        if service is None:
            raise LookupError("Услуга справочника не найдена")
        item.service_id = service_id
        item.match_method = MatchMethod.manual
        item.match_confidence = 1.0
        item.is_verified = True
        item.needs_review = False
        item.verification_note = note or (
            "Оператор подтвердил" if action == "confirm" else "Оператор исправил"
        )
        # Самообучение словаря синонимов.
        if learn_synonym(db, service, item.service_name_raw):
            learned = 1

    db.commit()
    return {
        "item_id": item.item_id,
        "service_id": item.service_id,
        "match_method": item.match_method.value,
        "match_confidence": item.match_confidence,
        "is_verified": item.is_verified,
        "synonyms_learned": learned,
    }


def rebuild_index(db: Session) -> LexicalIndex:
    return LexicalIndex.from_db(db)
