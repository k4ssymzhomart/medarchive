"""Добавить значение enum matchmethod = 'code' (Задача B, Level 0).

Для свежей БД значение уже создаётся через create_all в 0001 (модель содержит
MatchMethod.code), поэтому здесь IF NOT EXISTS делает операцию идемпотентной.
Для уже поднятой БД миграция добавляет значение в существующий enum тип.

Revision ID: 0002_matchmethod_code
Revises: 0001_initial
Create Date: 2026-06-27
"""

from __future__ import annotations

from alembic import op

revision = "0002_matchmethod_code"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE не может идти в одной транзакции с использованием
    # значения — выносим в autocommit блок.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE matchmethod ADD VALUE IF NOT EXISTS 'code'")


def downgrade() -> None:
    # Postgres не поддерживает удаление значения enum. Откат не предусмотрен.
    pass
