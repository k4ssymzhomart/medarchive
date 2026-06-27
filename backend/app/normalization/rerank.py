"""Реранкер (раздел 5.1, 8.2 уровень 4). Cohere Rerank 3.5.

Переупорядочивает топ кандидатов от эмбеддингов. Кэш в БД по хешу
(запрос + список документов). Без ключа возвращаем None — каскад использует
порядок эмбеддингов.
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

# Любой сбой сети/ответа AI = деградация на порядок эмбеддингов (issue #19).
_AI_ERRORS = (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError)


def _key(query: str, docs: list[str]) -> str:
    raw = "rerank:" + settings.rerank_model + ":" + query + "::" + "||".join(docs)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def rerank(db: Session, query: str, documents: list[str], top_n: int | None = None):
    """Возвращает список (index, score) по убыванию, или None если недоступно."""
    if not documents:
        return None
    key = _key(query, documents)
    row = db.execute(select(AICache).where(AICache.cache_key == key)).scalar_one_or_none()
    if row:
        return [(r["index"], r["score"]) for r in row.payload.get("results", [])]
    if not settings.cohere_api_key:
        return None

    try:
        resp = httpx.post(
            "https://api.cohere.com/v2/rerank",
            headers={"Authorization": f"Bearer {settings.cohere_api_key}"},
            json={
                "model": settings.rerank_model,
                "query": query,
                "documents": documents,
                "top_n": top_n or len(documents),
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        results = resp.json()["results"]
        parsed = [(r["index"], float(r["relevance_score"])) for r in results]
    except _AI_ERRORS as exc:
        log.warning("Реранк недоступен, используем порядок эмбеддингов: %s", exc)
        return None
    db.add(
        AICache(
            kind="rerank",
            cache_key=key,
            payload={"results": [{"index": i, "score": s} for i, s in parsed]},
        )
    )
    db.flush()
    return parsed
