"""Полнотекстовый поиск (раздел 10)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SearchResponse
from app.services.search_service import search

router = APIRouter()


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Поиск услуг и партнёров",
    description=(
        "Полнотекстовый поиск по названиям услуг и партнёров (PostgreSQL FTS, "
        "русская конфигурация, с фолбэком ILIKE). Цель времени ответа ниже 200 мс; "
        "фактическое время запроса возвращается в поле took_ms."
    ),
    response_description="Результаты поиска с рангом релевантности и временем запроса",
)
def search_endpoint(
    q: str = Query("", description="Поисковый запрос"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> SearchResponse:
    return search(db, q, limit=limit, offset=offset)
