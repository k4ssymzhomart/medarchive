"""Лексический матч (раздел 8.2, уровни 1-2). RapidFuzz, офлайн.

Строит индекс нормализованных названий и синонимов справочника. Точное
совпадение -> уверенность 1.0. Иначе token_sort_ratio/partial_ratio.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Service
from app.normalization.normalize import normalize, normalize_code


@dataclass
class LexEntry:
    service_id: uuid.UUID
    service_name: str
    category: str | None
    normalized: str  # ключ (имя или синоним)


class LexicalIndex:
    """Индекс нормализованных названий + синонимов. Строится из справочника."""

    def __init__(self) -> None:
        self.entries: list[LexEntry] = []
        self._exact: dict[str, LexEntry] = {}
        self._choices: list[str] = []
        # Карта код тарификатора -> список услуг (82 кода неуникальны, поэтому список).
        self._by_code: dict[str, list[LexEntry]] = {}

    @classmethod
    def from_db(cls, db: Session) -> LexicalIndex:
        services = db.execute(select(Service).where(Service.is_active.is_(True))).scalars().all()
        return cls.from_services(services)

    @classmethod
    def from_services(cls, services) -> LexicalIndex:
        """Строит индекс из любого итерируемого с полями service_id, service_name,
        synonyms, category, icd_code (БД или офлайн список для замера/тестов)."""
        idx = cls()
        for svc in services:
            names = [svc.service_name, *(getattr(svc, "synonyms", None) or [])]
            for nm in names:
                norm = normalize(nm)
                if not norm:
                    continue
                entry = LexEntry(svc.service_id, svc.service_name, getattr(svc, "category", None), norm)
                idx.entries.append(entry)
                idx._exact.setdefault(norm, entry)
            nc = normalize_code(getattr(svc, "icd_code", None))
            if nc:
                bucket = idx._by_code.setdefault(nc, [])
                if all(e.service_id != svc.service_id for e in bucket):
                    bucket.append(
                        LexEntry(svc.service_id, svc.service_name, getattr(svc, "category", None), nc)
                    )
        idx._choices = [e.normalized for e in idx.entries]
        return idx

    def exact(self, raw: str) -> LexEntry | None:
        return self._exact.get(normalize(raw))

    def by_code(self, code: str | None) -> list[LexEntry]:
        """Услуги справочника с данным кодом тарификатора (после нормализации)."""
        nc = normalize_code(code)
        if not nc:
            return []
        return list(self._by_code.get(nc, []))

    def search(self, raw: str, limit: int = 20, category: str | None = None):
        """Возвращает [(LexEntry, score 0..1)] по убыванию."""
        query = normalize(raw)
        if not query or not self._choices:
            return []
        scorer = fuzz.token_sort_ratio
        matches = process.extract(query, self._choices, scorer=scorer, limit=limit * 2)
        out: list[tuple[LexEntry, float]] = []
        seen: set[uuid.UUID] = set()
        for _choice, score, pos in matches:
            entry = self.entries[pos]
            if category and entry.category and normalize(entry.category) != normalize(category):
                continue
            if entry.service_id in seen:
                continue
            seen.add(entry.service_id)
            # комбинируем token_sort с partial_ratio для хвостов
            partial = fuzz.partial_ratio(query, entry.normalized)
            combined = max(score, 0.5 * score + 0.5 * partial) / 100.0
            out.append((entry, combined))
            if len(out) >= limit:
                break
        out.sort(key=lambda t: t[1], reverse=True)
        return out
