"""Интеграционные тесты эндпоинта поиска и замер времени (issue #5).

Полнотекстовый поиск (app/services/search_service.py) построен на сыром SQL
PostgreSQL: plainto_tsquery('russian', ...), to_tsvector, ts_rank, GIN-индекс.
Это невоспроизводимо на SQLite и в CI без Postgres/pgvector.

Поэтому контракт HTTP-эндпоинта /search (форма ответа, фильтры limit/offset,
пагинация, поле took_ms) проверяется с подменой слоя сервиса поиска
(app.api.search.search) через monkeypatch — изолированно от движка БД.
Прод-код не модифицируется.

Дополнительно — ЗАМЕР ВРЕМЕНИ: time.perf_counter вокруг вызова TestClient,
ассерт разумного потолка и печать метрики (видно в pytest -s).

Реальный путь к Postgres FTS закрыт тестом с pytest.mark.skipif: он
выполняется только если задан MEDPARTNERS_TEST_PG_URL на живой Postgres.
"""

from __future__ import annotations

import os
import time
import uuid

import pytest

import app.api.search as search_api
from app.schemas import SearchResponse, SearchResultItem


@pytest.fixture()
def fake_search(monkeypatch):
    """Подменяет слой поиска: эндпоинт отдаёт детерминированный результат.

    Возвращает список захваченных вызовов для проверки проброса параметров.
    """
    calls: list[dict] = []

    sid = uuid.uuid4()
    pid = uuid.uuid4()

    def _fake(db, query, limit=20, offset=0):  # noqa: ANN001, ANN202
        calls.append({"query": query, "limit": limit, "offset": offset})
        start = time.perf_counter()
        results: list[SearchResultItem] = []
        if (query or "").strip():
            pool = [
                SearchResultItem(
                    kind="service",
                    id=sid,
                    title="Глюкоза крови",
                    subtitle="Лаборатория",
                    category="Лаборатория",
                    rank=0.9,
                ),
                SearchResultItem(
                    kind="partner",
                    id=pid,
                    title="Клиника Альфа",
                    subtitle="Алматы",
                    category=None,
                    rank=0.5,
                ),
            ]
            results = pool[offset : offset + limit]
        took = (time.perf_counter() - start) * 1000.0
        return SearchResponse(
            query=(query or "").strip(),
            took_ms=round(took, 2),
            total=len(results),
            results=results,
        )

    monkeypatch.setattr(search_api, "search", _fake)
    return calls


def test_search_response_shape(client, fake_search):
    resp = client.get("/search", params={"q": "глюкоза"})
    assert resp.status_code == 200
    body = resp.json()
    # форма ответа SearchResponse
    assert set(body.keys()) == {"query", "took_ms", "total", "results"}
    assert body["query"] == "глюкоза"
    assert isinstance(body["took_ms"], (int, float))
    assert body["total"] == len(body["results"])
    if body["results"]:
        item = body["results"][0]
        assert set(item.keys()) == {"kind", "id", "title", "subtitle", "category", "rank"}
        assert item["kind"] in {"service", "partner"}


def test_search_empty_query_returns_empty(client, fake_search):
    resp = client.get("/search", params={"q": ""})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []


def test_search_default_params_passed(client, fake_search):
    client.get("/search", params={"q": "тест"})
    assert fake_search[-1] == {"query": "тест", "limit": 20, "offset": 0}


def test_search_limit_offset_passed(client, fake_search):
    client.get("/search", params={"q": "тест", "limit": 5, "offset": 10})
    assert fake_search[-1] == {"query": "тест", "limit": 5, "offset": 10}


def test_search_pagination_slices(client, fake_search):
    full = client.get("/search", params={"q": "клиника", "limit": 20, "offset": 0}).json()
    assert full["total"] == 2
    page2 = client.get("/search", params={"q": "клиника", "limit": 1, "offset": 1}).json()
    assert page2["total"] == 1
    assert page2["results"][0]["id"] != full["results"][0]["id"]


def test_search_limit_validation_422(client, fake_search):
    # limit > 100 нарушает Query(le=100)
    assert client.get("/search", params={"q": "x", "limit": 1000}).status_code == 422
    # limit < 1 нарушает Query(ge=1)
    assert client.get("/search", params={"q": "x", "limit": 0}).status_code == 422
    # offset < 0 нарушает Query(ge=0)
    assert client.get("/search", params={"q": "x", "offset": -1}).status_code == 422


def test_search_missing_q_defaults_empty(client, fake_search):
    # q имеет дефолт "" -> валидно, пустой результат
    resp = client.get("/search")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# --------------------------------------------------------------------------- #
# ЗАМЕР ВРЕМЕНИ ПОИСКА (issue #5).
# Меряем сквозное время HTTP-запроса к /search через TestClient.
# Потолок намеренно щедрый (in-process TestClient), цель — поймать регрессии
# и зафиксировать метрику. Реальная цель сервиса < 200 мс (см. docstring сервиса).
# --------------------------------------------------------------------------- #
SEARCH_LATENCY_BUDGET_MS = 1000.0


def test_search_latency_measured(client, fake_search, capsys):
    """Замеряет время запроса и печатает метрику (видно при pytest -s)."""
    start = time.perf_counter()
    resp = client.get("/search", params={"q": "глюкоза"})
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert resp.status_code == 200

    # метрика времени присутствует в теле и неотрицательна
    body = resp.json()
    assert body["took_ms"] >= 0.0

    with capsys.disabled():
        print(
            f"\n[ЗАМЕР] /search сквозное время: {elapsed_ms:.2f} мс "
            f"(took_ms из тела: {body['took_ms']:.2f} мс)"
        )

    assert elapsed_ms < SEARCH_LATENCY_BUDGET_MS, (
        f"поиск слишком медленный: {elapsed_ms:.2f} мс > {SEARCH_LATENCY_BUDGET_MS} мс"
    )


def test_search_latency_p_median(client, fake_search, capsys):
    """Медиана по серии запросов — устойчивее единичного замера."""
    samples = []
    for _ in range(15):
        t0 = time.perf_counter()
        r = client.get("/search", params={"q": "клиника"})
        samples.append((time.perf_counter() - t0) * 1000.0)
        assert r.status_code == 200
    samples.sort()
    median = samples[len(samples) // 2]
    with capsys.disabled():
        print(
            f"\n[ЗАМЕР] /search медиана за {len(samples)} запросов: {median:.2f} мс "
            f"(min={samples[0]:.2f}, max={samples[-1]:.2f})"
        )
    assert median < SEARCH_LATENCY_BUDGET_MS


# --------------------------------------------------------------------------- #
# Реальный Postgres FTS: только при наличии живой БД. В CI пропускается.
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(
    not os.getenv("MEDPARTNERS_TEST_PG_URL"),
    reason="требует Postgres с русской FTS-конфигурацией (нет в CI); "
    "задайте MEDPARTNERS_TEST_PG_URL для запуска",
)
def test_search_real_postgres_fts():
    """Сквозной поиск на реальном Postgres: проверяет сырой SQL сервиса.

    Запускается только если задан MEDPARTNERS_TEST_PG_URL. Создаёт схему,
    сидит услугу/партнёра, ищет, замеряет время и сверяет потолок 200 мс.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models import Base, Partner, Service
    from app.services.search_service import search

    engine = create_engine(os.environ["MEDPARTNERS_TEST_PG_URL"], future=True)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as s:
            s.add(Service(service_name="Глюкоза крови", category="Лаборатория"))
            s.add(Partner(name="Клиника Альфа", city="Алматы"))
            s.commit()

            t0 = time.perf_counter()
            res = search(s, "глюкоза", limit=10, offset=0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            assert res.total >= 1
            assert any(r.title == "Глюкоза крови" for r in res.results)
            assert res.took_ms >= 0.0
            print(f"\n[ЗАМЕР PG] реальный FTS: {elapsed_ms:.2f} мс")
            assert elapsed_ms < 200.0
    finally:
        Base.metadata.drop_all(engine)
