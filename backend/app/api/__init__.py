"""Агрегация роутеров API."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import documents, partners, queues, search, services, stats

api_router = APIRouter()
api_router.include_router(services.router, tags=["services"])
api_router.include_router(partners.router, tags=["partners"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(queues.router, tags=["queues"])
api_router.include_router(documents.router, tags=["documents"])
api_router.include_router(stats.router, tags=["stats"])
