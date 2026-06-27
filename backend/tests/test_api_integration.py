"""Интеграционные тесты API на временной Postgres (issue #5).

Поднимает одноразовый pgvector Postgres (TEST_DATABASE_URL, иначе docker, иначе
тесты пропускаются), создаёт схему и сид, и гоняет все 14 эндпоинтов через
FastAPI TestClient. get_db подменяется на сессию тестовой БД, поэтому глобальный
engine приложения не трогается. Без ключей и без внешних сервисов: Celery/Redis
не нужны (upload с enqueue=False / подменой). В конце — замер p95 времени /search
на загруженной базе (критерий: ниже 200 мс).
"""

from __future__ import annotations

import datetime as dt
import os
import socket
import subprocess
import time
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

PG_IMAGE = "pgvector/pgvector:pg16"
PG_USER = "medp"
PG_PASSWORD = "medp_test"  # noqa: S105 — одноразовый локальный контейнер, не секрет
PG_DB = "medp_test"

# Словари для генерации «загруженной» базы под замер поиска.
_SERVICE_HEADS = [
    "Общий анализ", "Биохимический анализ", "Консультация", "УЗИ", "Рентген",
    "Компьютерная томография", "Магнитно резонансная томография", "Гастроскопия",
    "Колоноскопия", "Электрокардиография", "Спирография", "Маммография",
]
_SERVICE_TAILS = [
    "крови", "мочи", "терапевта", "хирурга", "кардиолога", "брюшной полости",
    "органов малого таза", "грудной клетки", "почек", "щитовидной железы",
    "коленного сустава", "сосудов шеи",
]
_CITIES = ["Алматы", "Астана", "Шымкент", "Караганда", "Актобе", "Тараз"]
_PARTNER_HEADS = ["Клиника", "Медицинский центр", "Госпиталь", "Лаборатория", "Диагностика"]


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _docker_ok() -> bool:
    try:
        return (
            subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            ).returncode
            == 0
        )
    except Exception:
        return False


def _wait_ready(url: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            eng = create_engine(url, future=True)
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            eng.dispose()
            return
        except Exception as exc:  # noqa: BLE001 — ждём готовности контейнера
            last = exc
            time.sleep(0.5)
    raise RuntimeError(f"Postgres не поднялся за {timeout}s: {last}")


@pytest.fixture(scope="session")
def pg_url():
    """URL тестовой Postgres: из TEST_DATABASE_URL, иначе одноразовый docker."""
    env_url = os.environ.get("TEST_DATABASE_URL")
    if env_url:
        _wait_ready(env_url)
        yield env_url
        return
    if not _docker_ok():
        pytest.skip("Нужна тестовая Postgres: задайте TEST_DATABASE_URL или запустите Docker")
    port = _free_port()
    cid = (
        subprocess.check_output(
            [
                "docker", "run", "-d", "--rm",
                "-e", f"POSTGRES_USER={PG_USER}",
                "-e", f"POSTGRES_PASSWORD={PG_PASSWORD}",
                "-e", f"POSTGRES_DB={PG_DB}",
                "-p", f"127.0.0.1:{port}:5432",
                PG_IMAGE,
            ]
        )
        .decode()
        .strip()
    )
    url = f"postgresql+psycopg://{PG_USER}:{PG_PASSWORD}@127.0.0.1:{port}/{PG_DB}"
    try:
        _wait_ready(url)
        yield url
    finally:
        subprocess.run(
            ["docker", "rm", "-f", cid],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


@pytest.fixture(scope="session")
def engine(pg_url):
    """Схема как в проде: расширение vector, таблицы из моделей, GIN FTS индексы."""
    import app.models  # noqa: F401 — регистрирует таблицы в Base.metadata
    from app.database import Base

    eng = create_engine(pg_url, future=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(eng)
    with eng.begin() as conn:
        # Индексы из миграции 0001, влияющие на поиск (hnsw на 3072 не создаём:
        # измерение выше лимита, в проде ANN-индекс тоже снят).
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_services_fts ON services "
                "USING gin (to_tsvector('russian', coalesce(service_name,'')))"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_partners_fts ON partners USING gin "
                "(to_tsvector('russian', coalesce(name,'') || ' ' || coalesce(city,'')))"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_items_history ON price_items "
                "(partner_id, service_id, effective_date)"
            )
        )
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def seed(engine) -> dict:
    """Курируемые сущности с известными id + «загруженная» база для замера поиска."""
    from app import models as m

    ids: dict = {}
    with Session(engine) as db:
        # --- курируемые сущности (известные id для адресных проверок) ---
        p_alfa = m.Partner(partner_id=uuid.uuid4(), name="Клиника Альфа", city="Алматы")
        p_beta = m.Partner(partner_id=uuid.uuid4(), name="Госпиталь Бета", city="Астана")
        db.add_all([p_alfa, p_beta])

        svc_blood = m.Service(
            service_id=uuid.uuid4(),
            service_name="Общий анализ крови",
            category="Гематология",
        )
        svc_therapist = m.Service(
            service_id=uuid.uuid4(),
            service_name="Консультация терапевта",
            category="Консультации",
        )
        db.add_all([svc_blood, svc_therapist])

        doc = m.PriceDocument(
            doc_id=uuid.uuid4(),
            partner_id=p_alfa.partner_id,
            file_name="Клиника Альфа прайс 2026.pdf",
            file_format=m.FileFormat.pdf,
            file_hash=uuid.uuid4().hex,
            parse_status=m.ParseStatus.done,
            item_count=4,
            ocr_applied=False,
            processing_seconds=1.5,
        )
        db.add(doc)
        db.flush()

        # сопоставленная позиция (свежая) + её предыдущая версия — для истории цен
        matched_old = m.PriceItem(
            item_id=uuid.uuid4(), doc_id=doc.doc_id, partner_id=p_alfa.partner_id,
            service_id=svc_blood.service_id, service_name_raw="ОАК",
            price_resident_kzt=Decimal("1800.00"), effective_date=dt.date(2024, 1, 1),
            is_active=False, is_verified=True, match_method=m.MatchMethod.exact,
            match_confidence=1.0,
        )
        matched_new = m.PriceItem(
            item_id=uuid.uuid4(), doc_id=doc.doc_id, partner_id=p_alfa.partner_id,
            service_id=svc_blood.service_id, service_name_raw="Общий анализ крови (ОАК)",
            price_resident_kzt=Decimal("2200.00"), effective_date=dt.date(2026, 1, 1),
            is_active=True, is_verified=True, match_method=m.MatchMethod.exact,
            match_confidence=1.0,
        )
        unmatched = m.PriceItem(
            item_id=uuid.uuid4(), doc_id=doc.doc_id, partner_id=p_alfa.partner_id,
            service_id=None, service_name_raw="кровь развернуто",
            price_resident_kzt=Decimal("3000.00"), is_active=True,
            needs_review=False, match_method=m.MatchMethod.none, match_confidence=0.5,
        )
        # needs_review/anomaly ссылаются на ДРУГУЮ услугу, чтобы не засорять
        # историю цен пары (Альфа, Общий анализ крови).
        needs_review = m.PriceItem(
            item_id=uuid.uuid4(), doc_id=doc.doc_id, partner_id=p_alfa.partner_id,
            service_id=svc_therapist.service_id, service_name_raw="приём терапевта?",
            price_resident_kzt=Decimal("2500.00"), is_active=True,
            needs_review=True, match_method=m.MatchMethod.fuzzy, match_confidence=0.7,
        )
        anomaly = m.PriceItem(
            item_id=uuid.uuid4(), doc_id=doc.doc_id, partner_id=p_alfa.partner_id,
            service_id=svc_therapist.service_id, service_name_raw="приём срочно",
            price_resident_kzt=Decimal("999999.00"), is_active=True,
            is_anomaly=True, match_method=m.MatchMethod.exact, match_confidence=1.0,
        )
        db.add_all([matched_old, matched_new, unmatched, needs_review, anomaly])
        db.flush()

        # кандидат для несопоставленной позиции (очередь оператора + /match)
        db.add(
            m.ServiceMatchCandidate(
                candidate_id=uuid.uuid4(), item_id=unmatched.item_id,
                service_id=svc_blood.service_id, score=0.82,
                method=m.MatchMethod.fuzzy, rank=1,
            )
        )

        # --- «загруженная» база для честного замера поиска ---
        bulk_partners = []
        for i in range(250):
            bulk_partners.append(
                m.Partner(
                    name=f"{_PARTNER_HEADS[i % len(_PARTNER_HEADS)]} "
                    f"{_CITIES[i % len(_CITIES)]} {i}",
                    city=_CITIES[i % len(_CITIES)],
                )
            )
        db.add_all(bulk_partners)

        bulk_services = []
        for i in range(1500):
            head = _SERVICE_HEADS[i % len(_SERVICE_HEADS)]
            tail = _SERVICE_TAILS[(i // len(_SERVICE_HEADS)) % len(_SERVICE_TAILS)]
            bulk_services.append(
                m.Service(service_name=f"{head} {tail} {i}", category=head)
            )
        db.add_all(bulk_services)
        db.flush()

        bulk_docs = []
        for p in bulk_partners:
            bulk_docs.append(
                m.PriceDocument(
                    partner_id=p.partner_id,
                    file_name=f"{p.name} прайс.xlsx",
                    file_format=m.FileFormat.xlsx,
                    file_hash=uuid.uuid4().hex,
                    parse_status=m.ParseStatus.done,
                )
            )
        db.add_all(bulk_docs)
        db.flush()

        bulk_items = []
        for i in range(3000):
            p = bulk_partners[i % len(bulk_partners)]
            d = bulk_docs[i % len(bulk_docs)]
            s = bulk_services[i % len(bulk_services)]
            bulk_items.append(
                m.PriceItem(
                    doc_id=d.doc_id, partner_id=p.partner_id, service_id=s.service_id,
                    service_name_raw=s.service_name,
                    price_resident_kzt=Decimal(str(1000 + (i % 50) * 100)),
                    is_active=True, match_method=m.MatchMethod.exact, match_confidence=1.0,
                )
            )
        db.add_all(bulk_items)
        db.commit()

        ids = {
            "partner_alfa": p_alfa.partner_id,
            "partner_beta": p_beta.partner_id,
            "service_blood": svc_blood.service_id,
            "service_therapist": svc_therapist.service_id,
            "doc": doc.doc_id,
            "item_matched": matched_new.item_id,
            "item_unmatched": unmatched.item_id,
        }
    with engine.begin() as conn:
        conn.execute(text("ANALYZE"))
    return ids


@pytest.fixture(scope="session")
def client(engine, seed):
    """TestClient с подменой get_db на сессию тестовой БД."""
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============================ системные эндпоинты ============================


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body and "ai_enabled" in body


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["docs"] == "/docs"


# ============================ services ============================


def test_list_services(client, seed):
    r = client.get("/services", params={"limit": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["page"]["total"] >= 1500
    assert len(body["items"]) == 10
    assert {"service_id", "service_name"} <= body["items"][0].keys()


def test_list_services_filter_q(client):
    r = client.get("/services", params={"q": "терапевта", "limit": 50})
    assert r.status_code == 200
    assert any("терапевт" in it["service_name"].lower() for it in r.json()["items"])


def test_service_partners(client, seed):
    r = client.get(f"/services/{seed['service_blood']}/partners")
    assert r.status_code == 200
    rows = r.json()
    assert any(row["partner_name"] == "Клиника Альфа" for row in rows)


def test_service_partners_404(client):
    r = client.get(f"/services/{uuid.uuid4()}/partners")
    assert r.status_code == 404


# ============================ partners ============================


def test_list_partners(client, seed):
    r = client.get("/partners", params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["page"]["total"] >= 250
    assert len(body["items"]) == 5


def test_list_partners_filter_city(client):
    r = client.get("/partners", params={"city": "Астана", "limit": 100})
    assert r.status_code == 200
    assert all(it["city"] == "Астана" for it in r.json()["items"])


def test_partner_services(client, seed):
    r = client.get(f"/partners/{seed['partner_alfa']}/services")
    assert r.status_code == 200
    body = r.json()
    assert body["page"]["total"] >= 1
    assert all("service_name_raw" in it for it in body["items"])


def test_partner_services_404(client):
    r = client.get(f"/partners/{uuid.uuid4()}/services")
    assert r.status_code == 404


def test_price_history(client, seed):
    r = client.get(
        f"/partners/{seed['partner_alfa']}/services/{seed['service_blood']}/history"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["service_name"] == "Общий анализ крови"
    # две версии цены: старая (неактивная) и новая
    assert len(body["points"]) == 2
    assert body["points"][-1]["pct_change"] is not None


# ============================ search ============================


def test_search_returns_results(client, seed):
    r = client.get("/search", params={"q": "анализ крови", "limit": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "анализ крови"
    assert body["total"] >= 1
    assert "took_ms" in body
    kinds = {it["kind"] for it in body["results"]}
    assert kinds <= {"service", "partner"}


def test_search_empty_query(client):
    r = client.get("/search", params={"q": ""})
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_search_partner_hit(client):
    r = client.get("/search", params={"q": "Госпиталь Бета"})
    assert r.status_code == 200
    assert any(it["kind"] == "partner" for it in r.json()["results"])


# ============================ queues ============================


def test_unmatched_default(client, seed):
    r = client.get("/unmatched", params={"limit": 100})
    assert r.status_code == 200
    body = r.json()
    assert body["page"]["total"] >= 1
    item = next(it for it in body["items"] if it["item_id"] == str(seed["item_unmatched"]))
    assert item["partner_name"] == "Клиника Альфа"
    assert len(item["candidates"]) >= 1


def test_unmatched_modes(client):
    for mode in ("all", "unmatched", "needs_review", "anomaly"):
        r = client.get("/unmatched", params={"mode": mode})
        assert r.status_code == 200, mode


def test_unmatched_bad_mode_422(client):
    r = client.get("/unmatched", params={"mode": "wrong"})
    assert r.status_code == 422


def test_match_confirm(client, seed):
    payload = {
        "item_id": str(seed["item_unmatched"]),
        "service_id": str(seed["service_blood"]),
        "action": "confirm",
    }
    r = client.post("/match", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["match_method"] == "manual"
    assert body["is_verified"] is True
    assert body["service_id"] == str(seed["service_blood"])


def test_match_item_404(client, seed):
    payload = {"item_id": str(uuid.uuid4()), "service_id": str(seed["service_blood"])}
    r = client.post("/match", json=payload)
    assert r.status_code == 404


def test_match_bad_action_422(client, seed):
    payload = {"item_id": str(seed["item_unmatched"]), "action": "destroy"}
    r = client.post("/match", json=payload)
    assert r.status_code == 422


# ============================ documents ============================


def test_list_documents(client, seed):
    r = client.get("/documents")
    assert r.status_code == 200
    docs = r.json()
    assert any(d["doc_id"] == str(seed["doc"]) for d in docs)


def test_list_documents_filter_status(client):
    r = client.get("/documents", params={"status": "done"})
    assert r.status_code == 200
    assert all(d["parse_status"] == "done" for d in r.json())


def test_document_status(client, seed):
    r = client.get(f"/documents/{seed['doc']}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["parse_status"] == "done"
    assert body["item_count"] == 4


def test_document_status_404(client):
    r = client.get(f"/documents/{uuid.uuid4()}/status")
    assert r.status_code == 404


def test_upload_unsupported_extension(client):
    # Чистый путь без Celery/хранилища: неподдерживаемое расширение пропускается.
    r = client.post(
        "/upload",
        params={"enqueue": False},
        files={"file": ("readme.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["documents"] == []
    assert body["skipped_duplicates"] == []


def test_upload_maps_documents(client, monkeypatch, seed):
    # Подменяем ingest, чтобы проверить только маппинг ответа эндпоинта.
    from app.api import documents as documents_api

    class _Doc:
        def __init__(self):
            self.doc_id = uuid.uuid4()
            self.partner_id = None
            self.file_name = "p.xlsx"
            self.file_format = "xlsx"  # FileFormat(str, Enum) сериализуется в строку
            self.file_hash = uuid.uuid4().hex
            self.parse_status = "pending"
            self.effective_date = None
            self.item_count = 0
            self.page_count = None
            self.extractor_used = None
            self.ocr_applied = False
            self.created_at = dt.datetime.now(dt.UTC)

    def _fake_ingest(db, paths, enqueue=True):
        return [_Doc()], ["dup.xlsx"]

    monkeypatch.setattr(documents_api, "ingest_paths", _fake_ingest)
    r = client.post(
        "/upload",
        params={"enqueue": False},
        files={"file": ("p.xlsx", b"x", "application/octet-stream")},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["documents"]) == 1
    assert body["skipped_duplicates"] == ["dup.xlsx"]


# ============================ stats ============================


def test_stats(client, seed):
    r = client.get("/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["documents_total"] >= 1
    assert body["items_total"] >= 3000
    assert "by_format" in body


# ============================ OpenAPI / Swagger ============================


def test_openapi_documents_all_paths(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = spec["paths"]
    for p in ("/search", "/partners", "/services", "/unmatched", "/match",
              "/documents", "/stats", "/upload", "/health"):
        assert p in paths, p
    # каждая операция документирована summary (полировка Swagger)
    for path, ops in paths.items():
        for method, op in ops.items():
            if method in ("get", "post", "put", "patch", "delete"):
                assert op.get("summary"), f"нет summary у {method.upper()} {path}"
    # полировка: содержательные summary и задокументированные 404
    assert paths["/search"]["get"]["summary"] == "Поиск услуг и партнёров"
    assert paths["/search"]["get"].get("description")
    for path, method in (
        ("/match", "post"),
        ("/services/{service_id}/partners", "get"),
        ("/partners/{partner_id}/services", "get"),
        ("/documents/{doc_id}/status", "get"),
    ):
        assert "404" in paths[path][method]["responses"], f"нет 404 у {method} {path}"


def test_docs_ui_served(client):
    assert client.get("/docs").status_code == 200


# ============================ замер времени /search ============================

_PERF_QUERIES = [
    "анализ крови", "консультация", "УЗИ брюшной полости", "рентген",
    "томография", "терапевт", "Клиника Алматы", "щитовидной железы",
]
_TARGET_MS = 200.0
_PERF_REPEATS = 8  # на запрос -> 64 замера, хватает для p95


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return ordered[idx]


def test_search_p95_under_200ms(client, seed):
    """Критерий issue #5: p95 поиска ниже 200 мс на загруженной базе."""
    roundtrip: list[float] = []
    server: list[float] = []
    nonempty = 0
    for q in _PERF_QUERIES:  # прогрев планов запросов
        client.get("/search", params={"q": q})
    for _ in range(_PERF_REPEATS):
        for q in _PERF_QUERIES:
            start = time.perf_counter()
            r = client.get("/search", params={"q": q, "limit": 20})
            roundtrip.append((time.perf_counter() - start) * 1000.0)
            assert r.status_code == 200
            body = r.json()
            server.append(float(body["took_ms"]))
            nonempty += 1 if body["total"] > 0 else 0

    p95_server = _p95(server)
    p95_roundtrip = _p95(roundtrip)
    assert nonempty >= len(_PERF_QUERIES), f"слишком мало непустых ответов: {nonempty}"
    assert p95_server < _TARGET_MS, f"p95 серверного времени {p95_server:.1f} мс >= {_TARGET_MS}"
    assert p95_roundtrip < _TARGET_MS, f"p95 round-trip {p95_roundtrip:.1f} мс >= {_TARGET_MS}"
    print(
        f"\n/search p95: server={p95_server:.1f} мс, round-trip={p95_roundtrip:.1f} мс "
        f"(n={len(server)})"
    )
