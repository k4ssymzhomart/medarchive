"""Общая инфраструктура интеграционных тестов API (issue #5).

CI не поднимает Postgres/pgvector (см. .github/workflows/ci.yml: только pip +
ruff + pytest, без сервиса БД). Поэтому тестовая БД здесь — SQLite в памяти.

Модели проекта используют Postgres-специфичные типы (UUID, JSONB, pgvector.Vector).
Чтобы Base.metadata.create_all отработал на SQLite, ниже зарегистрированы
DDL-компиляторы, отображающие эти типы в SQLite-совместимые
(CHAR(36)/JSON/TEXT). Привязка значений в SQLAlchemy 2.0 деградирует корректно:
UUID остаётся uuid.UUID, JSONB круглит как list/dict, enum'ы и server_default
(func.now) работают. Это проверено для всех эндпоинтов, кроме полнотекстового
поиска (он на сыром SQL plainto_tsquery('russian', ...) — только Postgres;
для него в test_api_search.py используется подмена слоя сервиса поиска).

get_db подменяется через app.dependency_overrides на сессию к SQLite —
прод-код при этом не трогается.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pgvector.sqlalchemy import Vector
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


# --------------------------------------------------------------------------- #
# DDL-компиляторы: Postgres-типы -> SQLite-совместимый DDL.
# Регистрируются один раз на импорт модуля (идемпотентно для прогона).
# --------------------------------------------------------------------------- #
@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(element, compiler, **kw):  # noqa: ANN001, ANN201
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # noqa: ANN001, ANN201
    return "JSON"


@compiles(Vector, "sqlite")
def _compile_vector_sqlite(element, compiler, **kw):  # noqa: ANN001, ANN201
    return "TEXT"


@pytest.fixture(scope="session")
def engine():
    """Один SQLite-движок в памяти на сессию тестов.

    StaticPool + общее соединение, чтобы :memory: жила между запросами
    TestClient (каждый запрос берёт сессию из того же пула).
    """
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _rec):  # noqa: ANN001, ANN202
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # Импорт моделей внутри фикстуры: компиляторы выше уже зарегистрированы.
    from app.models import Base

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture()
def db_session(engine) -> Generator[Session, None, None]:
    """Чистая сессия на каждый тест: данные откатываются после теста."""
    from app.models import Base

    # Полная очистка между тестами для изоляции.
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())

    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session) -> Generator[TestClient, None, None]:
    """TestClient с подменой get_db на тестовую SQLite-сессию.

    Прод-код (app.database.get_db) не модифицируется — только override.
    """
    from app.database import get_db
    from app.main import app

    def _override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass  # сессией владеет фикстура db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Сидеры данных. Возвращают идентификаторы для ассертов.
# --------------------------------------------------------------------------- #
@pytest.fixture()
def seed(db_session):
    """Минимальный, но связный набор: партнёры, услуги, документ, позиции.

    Покрывает ветки эндпоинтов: matched / unmatched / needs_review / anomaly,
    история цен (две версии), активные/неактивные позиции.
    """
    from app.models import (
        FileFormat,
        MatchMethod,
        ParseStatus,
        Partner,
        PriceDocument,
        PriceItem,
        Service,
    )

    ids: dict[str, uuid.UUID | list] = {}

    p_almaty = Partner(name="Клиника Альфа", city="Алматы", bin="123456789012", is_active=True)
    p_astana = Partner(name="Клиника Бета", city="Астана", is_active=True)
    p_inactive = Partner(name="Клиника Гамма", city="Алматы", is_active=False)
    db_session.add_all([p_almaty, p_astana, p_inactive])
    db_session.flush()

    svc_glucose = Service(
        service_name="Глюкоза крови",
        synonyms=["сахар крови"],
        category="Лаборатория",
        is_active=True,
    )
    svc_consult = Service(
        service_name="Прием терапевта первичный",
        synonyms=[],
        category="Консультации",
        is_active=True,
    )
    svc_inactive = Service(service_name="Устаревшая услуга", category="Архив", is_active=False)
    db_session.add_all([svc_glucose, svc_consult, svc_inactive])
    db_session.flush()

    doc = PriceDocument(
        partner_id=p_almaty.partner_id,
        file_name="alfa_price.xlsx",
        file_format=FileFormat.xlsx,
        file_hash="hash_alfa_1",
        parse_status=ParseStatus.done,
        item_count=4,
        processing_seconds=1.5,
    )
    doc_astana = PriceDocument(
        partner_id=p_astana.partner_id,
        file_name="beta_price.pdf",
        file_format=FileFormat.pdf,
        file_hash="hash_beta_1",
        parse_status=ParseStatus.done,
        item_count=1,
        processing_seconds=2.5,
    )
    db_session.add_all([doc, doc_astana])
    db_session.flush()

    # matched + verified
    item_matched = PriceItem(
        doc_id=doc.doc_id,
        partner_id=p_almaty.partner_id,
        service_name_raw="глюкоза крови",
        service_id=svc_glucose.service_id,
        price_resident_kzt=1500,
        match_method=MatchMethod.exact,
        match_confidence=0.99,
        is_verified=True,
        is_active=True,
        effective_date=date(2026, 1, 1),
    )
    # needs_review (есть service_id, но требует подтверждения)
    item_review = PriceItem(
        doc_id=doc.doc_id,
        partner_id=p_almaty.partner_id,
        service_name_raw="прием терапевта",
        service_id=svc_consult.service_id,
        price_resident_kzt=5000,
        match_method=MatchMethod.embedding,
        match_confidence=0.7,
        needs_review=True,
        is_active=True,
    )
    # unmatched (нет service_id, не в ревью)
    item_unmatched = PriceItem(
        doc_id=doc.doc_id,
        partner_id=p_almaty.partner_id,
        service_name_raw="загадочная процедура",
        service_id=None,
        price_resident_kzt=9000,
        match_method=MatchMethod.none,
        needs_review=False,
        is_active=True,
    )
    # anomaly
    item_anomaly = PriceItem(
        doc_id=doc.doc_id,
        partner_id=p_almaty.partner_id,
        service_name_raw="узи брюшной полости",
        service_id=svc_glucose.service_id,
        price_resident_kzt=99999,
        match_method=MatchMethod.fuzzy,
        match_confidence=0.8,
        is_anomaly=True,
        needs_review=True,
        is_active=True,
    )
    # вторая (более ранняя, архивная) версия глюкозы у того же партнёра -> история цен
    item_history_old = PriceItem(
        doc_id=doc.doc_id,
        partner_id=p_almaty.partner_id,
        service_name_raw="глюкоза крови",
        service_id=svc_glucose.service_id,
        price_resident_kzt=1200,
        match_method=MatchMethod.exact,
        is_active=False,
        effective_date=date(2025, 6, 1),
    )
    # позиция партнёра из Астаны
    item_astana = PriceItem(
        doc_id=doc_astana.doc_id,
        partner_id=p_astana.partner_id,
        service_name_raw="глюкоза",
        service_id=svc_glucose.service_id,
        price_resident_kzt=1800,
        match_method=MatchMethod.exact,
        is_verified=True,
        is_active=True,
    )
    db_session.add_all(
        [
            item_matched,
            item_review,
            item_unmatched,
            item_anomaly,
            item_history_old,
            item_astana,
        ]
    )
    db_session.commit()

    ids.update(
        partner_almaty=p_almaty.partner_id,
        partner_astana=p_astana.partner_id,
        partner_inactive=p_inactive.partner_id,
        service_glucose=svc_glucose.service_id,
        service_consult=svc_consult.service_id,
        service_inactive=svc_inactive.service_id,
        doc=doc.doc_id,
        doc_astana=doc_astana.doc_id,
        item_matched=item_matched.item_id,
        item_review=item_review.item_id,
        item_unmatched=item_unmatched.item_id,
        item_anomaly=item_anomaly.item_id,
        item_history_old=item_history_old.item_id,
        item_astana=item_astana.item_id,
    )
    return ids
