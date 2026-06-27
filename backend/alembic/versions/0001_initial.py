"""Начальная схема: pgvector, таблицы, индексы (раздел 6).

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-27
"""

from __future__ import annotations

from alembic import op

from app.config import settings
from app.database import Base
import app.models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # pgvector (раздел 5).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Все таблицы из metadata (раздел 6).
    Base.metadata.create_all(bind=bind)

    # 6.7 Индексы.
    # B-tree на (partner_id, service_id, effective_date) для истории.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_items_history "
        "ON price_items (partner_id, service_id, effective_date)"
    )
    # GIN на ts_vector для FTS по названиям (русская конфигурация).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_services_fts "
        "ON services USING gin (to_tsvector('russian', coalesce(service_name,'')))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_partners_fts "
        "ON partners USING gin (to_tsvector('russian', coalesce(name,'') || ' ' || coalesce(city,'')))"
    )
    # pgvector: ANN индекс (hnsw/ivfflat) поддерживает максимум 2000 измерений,
    # а text-embedding-3-large даёт 3072. При справочнике ~1300 услуг точный
    # KNN скан по косинусу занимает доли миллисекунды, поэтому ANN индекс не нужен.
    # Если справочник вырастет на порядки, добавьте halfvec индекс
    # (USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops)) и каст в запросе.


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_services_embedding")
    op.execute("DROP INDEX IF EXISTS ix_partners_fts")
    op.execute("DROP INDEX IF EXISTS ix_services_fts")
    op.execute("DROP INDEX IF EXISTS ix_items_history")
    Base.metadata.drop_all(bind=op.get_bind())
