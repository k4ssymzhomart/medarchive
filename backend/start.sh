#!/bin/sh
# Стартовый скрипт бэкенда для Render (free-тариф, без preDeployCommand).
# Выносим цепочку команд в файл, чтобы не зависеть от того, как Render парсит
# dockerCommand: цепочки через && в dockerCommand ломаются (вся строка уходит в
# одну команду -> "not found"). Скрипт запускается родным Docker CMD.
# Все шаги идемпотентны: alembic не трогает уже накатанную схему, seed делает
# upsert. $PORT задаёт Render (локально по умолчанию 8000).
set -e

echo "[start] alembic upgrade head"
alembic upgrade head

echo "[start] seed-reference"
python -m app.cli seed-reference 'Справочник услуг.xlsx'

echo "[start] uvicorn on port ${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
