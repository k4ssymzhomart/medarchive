"""Агрегация роутеров API.

Публичные роутеры (поиск, партнёры, услуги, статистика) открыты. Админские
(загрузка/статус документов и очередь оператора с ручным сопоставлением)
закрываются операторским токеном через зависимость require_operator
(раздел 4.2). Защита активна только при заданном OPERATOR_TOKEN.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import documents, partners, queues, search, services, stats
from app.api.security import require_operator

api_router = APIRouter()

# Публичные эндпоинты.
api_router.include_router(services.router, tags=["services"])
api_router.include_router(partners.router, tags=["partners"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(stats.router, tags=["stats"])

# Админские эндпоинты: загрузка и очередь оператора под операторским токеном.
api_router.include_router(
    queues.router, tags=["queues"], dependencies=[Depends(require_operator)]
)
api_router.include_router(
    documents.router, tags=["documents"], dependencies=[Depends(require_operator)]
)
