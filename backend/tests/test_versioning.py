"""Тесты версионирования, дедупликации и детектора аномалий (раздел 9.2, 9.3).

История = цепочка PriceItem для пары (партнёр, услуга): у старой версии
is_active=false и заполнен supersedes_item_id. Скачок цены > порога -> аномалия.

Версионирование завязано на SQL (фильтр по партнёру/услуге/is_active и сортировка
по дате), поэтому тесты гоняют реальную сессию SQLAlchemy на in-memory SQLite,
а не мок. Создаём только три нужные таблицы — справочник с JSONB/Vector в SQLite
не компилируется и здесь не нужен.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Base, Partner, PriceDocument, PriceItem
from app.validation.versioning import _price_of, apply_versioning, pct_change

_TABLES = [Partner.__table__, PriceDocument.__table__, PriceItem.__table__]


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=_TABLES)
    with Session(engine) as session:
        partner = Partner(partner_id=uuid.uuid4(), name="Клиника")
        doc = PriceDocument(
            doc_id=uuid.uuid4(),
            partner_id=partner.partner_id,
            file_name="price.pdf",
            file_format="pdf",
            file_hash="hash",
        )
        session.add_all([partner, doc])
        session.flush()
        session.partner_id = partner.partner_id  # type: ignore[attr-defined]
        session.doc_id = doc.doc_id  # type: ignore[attr-defined]
        yield session


def _add(db, service_id, price, effective, **kw):
    item = PriceItem(
        doc_id=db.doc_id,
        partner_id=db.partner_id,
        service_id=service_id,
        service_name_raw="услуга",
        price_resident_kzt=Decimal(str(price)) if price is not None else None,
        effective_date=effective,
        **kw,
    )
    db.add(item)
    db.flush()
    return item


# --------------------------------------------------------------------------- #
# pct_change — относительное изменение цены.
# --------------------------------------------------------------------------- #
def test_pct_change_basic():
    assert pct_change(Decimal("100"), Decimal("200")) == 1.0
    assert pct_change(Decimal("200"), Decimal("100")) == 0.5
    assert pct_change(Decimal("100"), Decimal("150")) == 0.5


def test_pct_change_none_and_zero():
    assert pct_change(None, Decimal("100")) is None
    assert pct_change(Decimal("100"), None) is None
    assert pct_change(Decimal("0"), Decimal("100")) is None  # деление на ноль


def test_pct_change_non_finite():
    assert pct_change(Decimal("NaN"), Decimal("100")) is None
    assert pct_change(Decimal("100"), Decimal("Infinity")) is None


# --------------------------------------------------------------------------- #
# _price_of — выбор цены для сравнения (первое заполненное поле).
# --------------------------------------------------------------------------- #
def test_price_of_prefers_resident():
    item = PriceItem(
        price_resident_kzt=Decimal("100"),
        price_nonresident_kzt=Decimal("200"),
        price_original=Decimal("300"),
    )
    assert _price_of(item) == Decimal("100")


def test_price_of_falls_through_to_original():
    item = PriceItem(price_resident_kzt=None, price_nonresident_kzt=None, price_original=Decimal("300"))
    assert _price_of(item) == Decimal("300")


def test_price_of_returns_zero_not_skip():
    # Decimal('0') ложен, но это заполненное поле — ``or`` ошибочно бы его пропустил.
    item = PriceItem(price_resident_kzt=Decimal("0"), price_nonresident_kzt=Decimal("200"))
    assert _price_of(item) == Decimal("0")


def test_price_of_all_none():
    item = PriceItem(price_resident_kzt=None, price_nonresident_kzt=None, price_original=None)
    assert _price_of(item) is None


# --------------------------------------------------------------------------- #
# apply_versioning — связывание версий.
# --------------------------------------------------------------------------- #
def test_first_version_no_predecessor(db):
    sid = uuid.uuid4()
    item = _add(db, sid, 100, date(2024, 1, 1))
    info = apply_versioning(db, item)
    assert info["superseded"] is False
    assert item.is_active is True
    assert item.supersedes_item_id is None


def test_service_id_none_is_noop(db):
    item = _add(db, None, 100, date(2024, 1, 1))
    info = apply_versioning(db, item)
    assert info == {"superseded": False, "anomaly": False, "pct_change": None, "duplicate": False}


def test_newer_version_supersedes_old(db):
    sid = uuid.uuid4()
    old = _add(db, sid, 100, date(2024, 1, 1))
    new = _add(db, sid, 140, date(2025, 1, 1))
    info = apply_versioning(db, new)
    assert info["superseded"] is True
    assert old.is_active is False
    assert new.is_active is True
    assert new.supersedes_item_id == old.item_id


def test_anomaly_above_threshold(db):
    # 100 -> 200 = +100% > порога 50% -> аномалия.
    assert settings.anomaly_pct_threshold == 0.50
    sid = uuid.uuid4()
    _add(db, sid, 100, date(2024, 1, 1))
    new = _add(db, sid, 200, date(2025, 1, 1))
    info = apply_versioning(db, new)
    assert info["anomaly"] is True
    assert new.is_anomaly is True
    assert new.needs_review is True
    assert "Аномалия" in (new.verification_note or "")


def test_no_anomaly_below_threshold(db):
    # 100 -> 140 = +40% < 50% -> не аномалия.
    sid = uuid.uuid4()
    _add(db, sid, 100, date(2024, 1, 1))
    new = _add(db, sid, 140, date(2025, 1, 1))
    info = apply_versioning(db, new)
    assert info["anomaly"] is False
    assert new.is_anomaly is False


def test_anomaly_boundary_exactly_50_percent_is_not_anomaly(db):
    # Ровно 50% — порог строго «больше», поэтому НЕ аномалия (ТЗ: > 50%).
    sid = uuid.uuid4()
    _add(db, sid, 100, date(2024, 1, 1))
    new = _add(db, sid, 150, date(2025, 1, 1))
    info = apply_versioning(db, new)
    assert info["pct_change"] == 0.5
    assert info["anomaly"] is False


def test_anomaly_just_above_boundary(db):
    # 100 -> 151 = +51% -> аномалия.
    sid = uuid.uuid4()
    _add(db, sid, 100, date(2024, 1, 1))
    new = _add(db, sid, 151, date(2025, 1, 1))
    info = apply_versioning(db, new)
    assert info["anomaly"] is True


def test_duplicate_same_effective_date(db):
    sid = uuid.uuid4()
    old = _add(db, sid, 100, date(2024, 1, 1))
    new = _add(db, sid, 100, date(2024, 1, 1))
    info = apply_versioning(db, new)
    assert info["duplicate"] is True
    # Та же дата считается новее-или-равной: старую архивируем, новую оставляем.
    assert old.is_active is False
    assert new.is_active is True


def test_incoming_older_is_archived(db):
    sid = uuid.uuid4()
    _add(db, sid, 100, date(2025, 1, 1))  # уже есть свежая версия
    older = _add(db, sid, 90, date(2024, 1, 1))  # приходит более старая
    info = apply_versioning(db, older)
    assert info["superseded"] is False
    assert older.is_active is False  # архивируем входящую старую


def test_different_partner_is_isolated(db):
    sid = uuid.uuid4()
    existing = _add(db, sid, 100, date(2024, 1, 1))
    other = PriceItem(
        doc_id=db.doc_id,
        partner_id=uuid.uuid4(),  # другой партнёр
        service_id=sid,
        service_name_raw="услуга",
        price_resident_kzt=Decimal("999"),
        effective_date=date(2025, 1, 1),
    )
    db.add(other)
    db.flush()
    info = apply_versioning(db, other)
    assert info["superseded"] is False
    assert existing.is_active is True  # чужого партнёра не трогаем


def test_picks_newest_active_predecessor(db):
    sid = uuid.uuid4()
    v1 = _add(db, sid, 100, date(2022, 1, 1))
    v1.is_active = False  # уже архивная — её не выбираем
    v2 = _add(db, sid, 110, date(2023, 1, 1))
    db.flush()
    new = _add(db, sid, 130, date(2024, 1, 1))
    apply_versioning(db, new)
    # Предшественник — самый свежий активный (v2), а не архивный v1.
    assert new.supersedes_item_id == v2.item_id
    assert v2.is_active is False
