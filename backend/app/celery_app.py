"""Celery приложение (раздел 4.1). Параллельная обработка документов."""

from __future__ import annotations

from celery import Celery

from app.config import settings

celery = Celery(
    "medpartners",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.process"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,       # жёсткий лимит 10 мин (раздел 15: 85-стр PDF)
    task_soft_time_limit=540,
    worker_max_tasks_per_child=20,
)
