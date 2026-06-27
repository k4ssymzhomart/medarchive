"""Метрики дашборда и отчёт о качестве (раздел 10, 16)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import StatsResponse
from app.services.stats_service import build_stats

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
def stats(db: Session = Depends(get_db)) -> StatsResponse:
    return build_stats(db)
