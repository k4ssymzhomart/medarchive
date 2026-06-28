# MedPartners

Конвейер доверия к данным прайсов клиник. Система превращает хаотичный архив
прайсов в единую верифицированную базу услуг и цен с полным аудитом
происхождения каждой цифры: из какого файла, страницы и строки она извлечена,
с какой уверенностью сопоставлена, и как менялась во времени.

Архитектура и стратегия описаны в [PHASE_1_STRATEGY_AND_ARCHITECTURE.md](PHASE_1_STRATEGY_AND_ARCHITECTURE.md).

## Живой URL

Деплой на Render одним Blueprint (см. раздел «Деплой на Render»). После Apply:

- Лендинг: `https://medpartners-frontend.onrender.com/`
- Продукт: `https://medpartners-frontend.onrender.com/app`
- API и Swagger: `https://medpartners-backend.onrender.com/docs`
- Метрики: `https://medpartners-backend.onrender.com/stats`

Фактический URL впишите сюда после первого Apply (Render может добавить суффикс к имени, если оно занято).

## Что внутри

- Извлечение из 5 форматов через паттерн Стратегия: PDF текст, PDF скан с
  переOCR, XLSX, XLS (через LibreOffice), DOCX с принятием правок.
- Таблицы без линий разметки разбираются кластеризацией слов по координатам.
- Детектор битого встроенного OCR слоя и переOCR на Tesseract с русским языком.
- Нормализация каскадом: точный матч, RapidFuzz, облачные эмбеддинги (pgvector),
  реранкер, LLM арбитр. Без AI ключей каскад изящно деградирует до RapidFuzz.
- Валидация по всем проверкам ТЗ, детектор аномалий цен, бессрочное
  версионирование, дедупликация.
- REST API на FastAPI с авто OpenAPI/Swagger, полнотекстовый поиск на русской
  конфигурации Postgres.
- Фронтенд на React: поиск, страница партнёра, админка, очередь верификации,
  очередь несопоставленных, живой дашборд качества.

## Стек

FastAPI, PostgreSQL 16 с pgvector и FTS, Celery с Redis, React с Vite и
TypeScript, Docker. Подробное обоснование в разделе 5 документа стратегии.

## Быстрый старт (Docker)

```bash
cp .env.example .env
# по желанию впишите ключи OPENAI_API_KEY / COHERE_API_KEY / ANTHROPIC_API_KEY
docker compose up --build
```

Поднимутся пять сервисов: postgres, redis, backend, worker, frontend.

- Frontend: http://localhost:5173
- API + Swagger: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json

Backend на старте применяет миграции и сидирует синтетический справочник.

## Деплой на Render (Blueprint)

Проект разворачивается одним Blueprint из `render.yaml`: managed Postgres
(pgvector), Redis, бэкенд (Docker web, слушает `$PORT`, health `/health`),
Celery-воркер и фронтенд (static site). Подробности и фолбэки в
[DEPLOY_RENDER.md](DEPLOY_RENDER.md).

Три шага владельца в дашборде Render:

1. New → Blueprint → подключить репозиторий `k4ssymzhomart/medarchive`, ветка `main`.
2. Ввести секреты `OPENAI_API_KEY` / `COHERE_API_KEY` / `ANTHROPIC_API_KEY` (sync: false,
   в репозиторий не коммитятся). Все опциональны: без них работают код-матч, точное,
   fuzzy и FTS-поиск; с `OPENAI_API_KEY` включаются эмбеддинги и LLM-арбитр.
3. Apply и дождаться сборки (бэкенд-образ тяжёлый: Tesseract rus + LibreOffice + poppler).

Свежая Render-БД пустая. Чтобы живое демо сразу показывало реальные данные без
тяжёлого OCR на Render, восстановите дамп локальной наполненной БД:

```bash
# на машине с доступом к Render Postgres (строка подключения из дашборда)
pg_restore --no-owner --clean --if-exists -d "$RENDER_DATABASE_URL" medpartners_demo.dump
```

Адаптации под Render уже сделаны: бэкенд слушает `$PORT`; `DATABASE_URL` вида
`postgres://` нормализуется в `postgresql+psycopg://`; справочник и архив `docs/`
запечены в образ (`Dockerfile.render`).

## Обработка предоставленного архива

10 файлов лежат в `docs/`. Загрузить и обработать их можно двумя путями.

Через интерфейс: откройте админку, загрузите ZIP архива.

Через CLI внутри контейнера backend:

```bash
docker compose exec backend python -m app.cli ingest docs
docker compose exec backend python -m app.cli seed-reference
```

После прогона откройте дашборд: процент нормализации, разбивка по форматам,
размеры очередей это и есть живой отчёт о качестве.

## Локальная разработка без Docker

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# нужны системные tesseract-ocr-rus, poppler, libreoffice для OCR и .xls
export DATABASE_URL=postgresql+psycopg://medpartners:medpartners@localhost:5432/medpartners
alembic upgrade head
uvicorn app.main:app --reload
celery -A app.celery_app.celery worker --loglevel=info   # в отдельном окне
```

Frontend:

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, проксирует /api на :8000
```

## Тесты

```bash
cd backend && pytest
```

## Структура

```
backend/
  app/
    api/            REST роутеры (services, partners, search, queues, documents, stats)
    pipeline/       извлечение: router, экстракторы, columns, price_parser, ocr, textquality
    normalization/  каскад сопоставления, эмбеддинги, реранкер, LLM, загрузчик справочника
    validation/     проверки, аномалии, версионирование
    services/       оркестрация документов, поиск, статистика, партнёры, загрузка
    tasks/          Celery задачи
    models/         схема БД (SQLAlchemy)
    schemas/        контракт API (Pydantic)
  alembic/          миграции
frontend/
  src/
    pages/          экраны
    components/      Layout и UI примитивы
    lib/            типизированный API клиент и форматтеры
docs/               предоставленный архив из 10 файлов (не трогаем)
docs_report/        шаблон отчёта о качестве, презентация, демо сценарий
```

## Документация API

FastAPI генерирует OpenAPI автоматически: `/docs` (Swagger UI), `/redoc`,
`/openapi.json`. Все эндпоинты из раздела 10 документа стратегии.

## Надёжность демо

Ответы эмбеддингов и реранка кэшируются в БД по хешу текста. При сбое сети или
отсутствии AI ключей система продолжает работать на кэше плюс лексический
RapidFuzz, а уже обработанная база и поиск доступны полностью.
