"""Эмбеддинги (раздел 5.1, 8.2 уровень 3).

Облачный кандидатогенератор (OpenAI text-embedding-3-large по умолчанию).
Все ответы кэшируются в БД по хешу текста (AICache) — надёжность демо при
сбое сети. Без ключа возвращаем None: каскад продолжает на RapidFuzz.
"""

from __future__ import annotations

import hashlib
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AICache

log = logging.getLogger(__name__)

# Любой сбой сети/ответа AI = деградация на лексику, документ не падает (issue #19).
_AI_ERRORS = (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError)


def _key(text: str) -> str:
    raw = f"emb:{settings.embeddings_model}:{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_get(db: Session, key: str) -> list[float] | None:
    row = db.execute(select(AICache).where(AICache.cache_key == key)).scalar_one_or_none()
    if row:
        return row.payload.get("vector")
    return None


def _cache_put(db: Session, key: str, vector: list[float]) -> None:
    db.add(AICache(kind="embedding", cache_key=key, payload={"vector": vector}))
    db.flush()


def embed_text(db: Session, text: str) -> list[float] | None:
    """Один эмбеддинг с кэшем. None => AI недоступен (фолбэк на лексику)."""
    text = (text or "").strip()
    if not text:
        return None
    key = _key(text)
    cached = _cache_get(db, key)
    if cached is not None:
        return cached
    if not settings.openai_api_key:
        return None
    try:
        vector = _call_openai([text])[0]
    except _AI_ERRORS as exc:
        log.warning("Эмбеддинги недоступны, фолбэк на лексику: %s", exc)
        return None
    _cache_put(db, key, vector)
    return vector


def embed_batch(db: Session, texts: list[str]) -> list[list[float] | None]:
    """Пакетные эмбеддинги (для загрузки справочника). Использует кэш."""
    results: list[list[float] | None] = [None] * len(texts)
    to_fetch: list[tuple[int, str]] = []
    for i, t in enumerate(texts):
        t = (t or "").strip()
        if not t:
            continue
        cached = _cache_get(db, _key(t))
        if cached is not None:
            results[i] = cached
        else:
            to_fetch.append((i, t))

    if to_fetch and settings.openai_api_key:
        try:
            vectors = _call_openai([t for _, t in to_fetch])
        except _AI_ERRORS as exc:
            log.warning("Пакетные эмбеддинги недоступны, фолбэк на лексику: %s", exc)
            return results
        for (i, t), vec in zip(to_fetch, vectors):
            results[i] = vec
            _cache_put(db, _key(t), vec)
    return results


def _call_openai(texts: list[str]) -> list[list[float]]:
    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json={"model": settings.embeddings_model, "input": texts},
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    data.sort(key=lambda d: d["index"])
    return [d["embedding"] for d in data]
