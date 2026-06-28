# Деплой MedServicePrice на Render

Быстрый путь для демо. Поднимает: **Postgres (pgvector)** + **бэкенд** (FastAPI,
конвейер нормализации, Docker) + **фронтенд** (лендинг `/` и продукт `/app`,
статический сайт). Конфиг — в `render.yaml` (Blueprint).

Идентичность коммитов: `k4ssymzhomart <kassymzhomart.shubay@nu.edu.kz>`. Секреты
только в дашборде Render, в репозиторий не коммитятся.

---

## Вариант A — Blueprint (рекомендуется, один экран)

1. Render Dashboard → **New** → **Blueprint**.
2. Подключить репозиторий `k4ssymzhomart/medarchive`, ветка с этим файлом
   (`deploy/render` или `main` после мёрджа).
3. Render прочитает `render.yaml` и предложит создать 3 ресурса:
   `medpartners-db`, `medpartners-backend`, `medpartners-frontend`. Подтвердить.
4. Задать переменные с `sync: false` (см. раздел «Переменные»). Все опциональны —
   без ключей бэкенд всё равно поднимается (код-матч + точное + fuzzy + FTS-поиск).
5. **Apply**. Render соберёт образы, создаст БД, прогонит миграции и сид справочника
   (`preDeployCommand`), поднимет сервисы.

После сборки:
- Бэкенд: `https://medpartners-backend.onrender.com/docs` (Swagger), `/health`.
- Фронтенд: `https://medpartners-frontend.onrender.com/` (лендинг), `/app` (продукт).

---

## Переменные окружения (это и есть «.env» на Render)

Бэкенд (`medpartners-backend`). `DATABASE_URL` подставляется автоматически из БД,
остальное — ниже. Ключи задаются в дашборде (Environment), не в коде.

| Переменная | Значение | Обязательна |
|---|---|---|
| `DATABASE_URL` | из БД (Blueprint подставит) | да (авто) |
| `API_CORS_ORIGINS` | URL фронта, напр. `https://medpartners-frontend.onrender.com` | да |
| `LLM_ARBITER_MODEL` | `gpt-4o-mini` | нет |
| `OPENAI_API_KEY` | ключ OpenAI (эмбеддинги + арбитр) | нет* |
| `COHERE_API_KEY` | ключ Cohere (rerank) | нет** |
| `ANTHROPIC_API_KEY` | — | нет |

\* Без `OPENAI_API_KEY` семантическая нормализация (эмбеддинги/арбитр) выключается
gracefully; работают код-матч, точное совпадение, fuzzy и полнотекстовый поиск.
Сид справочника пройдёт, но без эмбеддингов услуг.

\** **Cohere-ключ сейчас trial** (лимит 10 запросов/мин, 1000/мес) — для bulk
rerank непригоден, rerank gracefully пропускается. Включать только с prod-ключом.

Фронтенд (`medpartners-frontend`), переменная сборки:

| Переменная | Значение |
|---|---|
| `VITE_API_URL` | URL бэкенда, напр. `https://medpartners-backend.onrender.com` |

`VITE_API_URL` инлайнится в бандл на этапе `npm run build`. При смене URL бэкенда
фронт нужно пересобрать (Render → Manual Deploy → Clear cache & deploy).

---

## Демо-данные (опционально, для показа продукта /app с реальными цифрами)

`preDeployCommand` уже грузит справочник (1231 услуга). Чтобы наполнить базу
реальными прайсами (10 файлов уже в образе, `/app/docs`):

Render → `medpartners-backend` → **Shell**:
```
python -m app.cli ingest docs        # извлечение 10 файлов (OCR/LibreOffice, медленно ~5-10 мин)
```
Лендинг `/` работает и без этого шага (цифры на нём статические и реальные).

---

## Вариант B — вручную через дашборд (если Blueprint не подошёл)

1. **New → PostgreSQL**: имя `medpartners-db`, версия 16. Скопировать Internal
   Database URL.
2. **New → Web Service** (бэкенд): репозиторий, **Docker**, `Dockerfile.render`,
   Root `.`. Health check `/health`. Pre-Deploy:
   `alembic upgrade head && python -m app.cli seed-reference 'Справочник услуг.xlsx'`.
   Env: `DATABASE_URL` (вставить из шага 1), `API_CORS_ORIGINS`, ключи.
3. **New → Static Site** (фронт): Root `frontend`, Build `npm install && npm run build`,
   Publish `dist`. Env `VITE_API_URL` = URL бэкенда. Rewrite `/*` → `/index.html`.

---

## Что важно знать (готчи)

- **URL-связки.** Бэк должен пускать домен фронта (`API_CORS_ORIGINS`), фронт
  должен звать домен бэка (`VITE_API_URL`). Если Render добавил суффикс к именам —
  поправь обе переменные на фактические адреса и пересобери фронт.
- **Драйвер БД.** Render даёт `postgresql://...`; приложение само приводит схему к
  `postgresql+psycopg://` (psycopg3) — правка в `app/config.py`, ничего делать не надо.
- **pgvector.** Расширение создаёт миграция `0001` (`CREATE EXTENSION IF NOT EXISTS
  vector`). Managed Postgres на Render это поддерживает. ANN-индекс не используется
  (точный KNN при ~1231 услуге), 3072-мерные эмбеддинги работают без hnsw.
- **Диск/хранилище.** `STORAGE_BACKEND=local` пишет в `/data/storage` (эфемерно на
  free-плане — загруженные файлы не переживут рестарт; для демо ок). Для постоянного
  хранения подключить Render Disk (платный план) или S3 (`STORAGE_BACKEND=s3`).
- **Воркер/Redis не нужны** для базового демо: CLI `ingest` синхронный (без Celery).
  Асинхронная загрузка через UI потребует Redis + worker (можно добавить позже).
- **Холодный старт free-плана** усыпляет сервис; первый запрос после простоя
  медленный — открой бэкенд за пару минут до показа.
