"""FastAPI приложение. Авто OpenAPI/Swagger закрывает критерий документации API."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.config import settings

logger = logging.getLogger(__name__)

if not settings.operator_token:
    # Заметный сигнал в логах: иначе случайный деплой без OPERATOR_TOKEN тихо
    # оставит админские эндпоинты (загрузка, сопоставление, очереди) открытыми.
    logger.warning(
        "OPERATOR_TOKEN не задан — админские эндпоинты ОТКРЫТЫ. "
        "Задайте OPERATOR_TOKEN, чтобы закрыть админку."
    )

app = FastAPI(
    title="MedServicePrice API",
    version=__version__,
    description=(
        "Конвейер доверия к данным прайсов клиник. Каждая цифра имеет "
        "происхождение, статус проверки и историю. OpenAPI генерируется автоматически."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "version": __version__, "ai_enabled": settings.ai_enabled}


@app.get("/", tags=["system"])
def root() -> dict:
    return {
        "name": "MedServicePrice API",
        "version": __version__,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
