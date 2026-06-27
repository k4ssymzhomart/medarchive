"""LLM арбитр (раздел 5.1, 8.2 уровень 5).

Только для пограничной зоны. На вход исходное название, категория и топ 3
кандидата справочника. На выход выбор кандидата (или «нет совпадения») и
короткое обоснование, которое мы пишем в verification_note. Кэш в БД.
Без ключа возвращаем None — позиция уходит в needs_review.
"""

from __future__ import annotations

import hashlib
import json

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AICache

_SYSTEM = (
    "Ты медицинский эксперт по нормализации названий услуг. Тебе дают исходное "
    "название услуги из прайса клиники и пронумерованный список кандидатов из "
    "справочника. Выбери НОМЕР единственного кандидата, который означает ту же "
    "услугу, либо 0 если совпадения нет. Ответь строго JSON: "
    '{"choice": <int>, "confidence": <0..1>, "reason": "<коротко по-русски>"}.'
)


def _key(query: str, candidates: list[str]) -> str:
    raw = "llm:" + settings.llm_model + ":" + query + "::" + "||".join(candidates)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def arbitrate(db: Session, query: str, category: str | None, candidates: list[str]) -> dict | None:
    """Возвращает {choice:int(1-based,0=нет), confidence:float, reason:str} или None."""
    if not candidates:
        return None
    key = _key(query, candidates)
    row = db.execute(select(AICache).where(AICache.cache_key == key)).scalar_one_or_none()
    if row:
        return row.payload
    if not settings.anthropic_api_key:
        return None

    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(candidates))
    prompt = (
        f"Исходное название: {query}\n"
        f"Категория: {category or 'неизвестно'}\n"
        f"Кандидаты:\n{numbered}\n\nОтвет JSON:"
    )
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": settings.llm_model,
            "max_tokens": 300,
            "system": _SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=45.0,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"]
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        payload = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        payload = {"choice": 0, "confidence": 0.0, "reason": "LLM вернул неразборчивый ответ"}

    db.add(AICache(kind="llm", cache_key=key, payload=payload))
    db.flush()
    return payload
