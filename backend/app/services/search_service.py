"""Полнотекстовый поиск (раздел 10). PostgreSQL FTS, русская конфигурация.

Цель времени ответа < 200 мс. Использует GIN индекс на to_tsvector('russian', ...)
из миграции, с фолбэком на ILIKE для коротких/частичных запросов.
"""

from __future__ import annotations

import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas import SearchResponse, SearchResultItem

_SQL = text(
    """
    WITH q AS (SELECT plainto_tsquery('russian', :query) AS tsq)
    SELECT 'service' AS kind, s.service_id AS id, s.service_name AS title,
           s.category AS subtitle, s.category AS category,
           ts_rank(to_tsvector('russian', coalesce(s.service_name,'')), q.tsq) AS rank
    FROM services s, q
    WHERE to_tsvector('russian', coalesce(s.service_name,'')) @@ q.tsq
       OR s.service_name ILIKE :like
    UNION ALL
    SELECT 'partner' AS kind, p.partner_id AS id, p.name AS title,
           p.city AS subtitle, NULL AS category,
           ts_rank(to_tsvector('russian', coalesce(p.name,'') || ' ' || coalesce(p.city,'')), q.tsq) AS rank
    FROM partners p, q
    WHERE to_tsvector('russian', coalesce(p.name,'') || ' ' || coalesce(p.city,'')) @@ q.tsq
       OR p.name ILIKE :like
    ORDER BY rank DESC
    LIMIT :limit OFFSET :offset
    """
)


def search(db: Session, query: str, limit: int = 20, offset: int = 0) -> SearchResponse:
    start = time.perf_counter()
    query = (query or "").strip()
    results: list[SearchResultItem] = []
    if query:
        rows = db.execute(
            _SQL,
            {"query": query, "like": f"%{query}%", "limit": limit, "offset": offset},
        ).mappings().all()
        for r in rows:
            results.append(
                SearchResultItem(
                    kind=r["kind"],
                    id=r["id"],
                    title=r["title"],
                    subtitle=r["subtitle"],
                    category=r["category"],
                    rank=float(r["rank"] or 0.0),
                )
            )
    took = (time.perf_counter() - start) * 1000.0
    return SearchResponse(query=query, took_ms=round(took, 2), total=len(results), results=results)
