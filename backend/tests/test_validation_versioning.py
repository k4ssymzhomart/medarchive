"""Тесты версионирования и дедупликации цен (разделы 9.2, 9.3).

apply_versioning связывает новую позицию с предыдущей версией той же пары
(партнёр, услуга): архивирует старую (is_active=false, supersedes_item_id),
помечает аномалию при скачке цены > порога, отмечает дубликаты по дате.

Сессия БД нужна (ORM-запросы), используется SQLite в памяти из conftest:
создаются только partners и price_items, чтобы обойти pgvector/JSONB.
Помощники _price_of и pct_change тестируются как чистые функции.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.config import settings
from app.models import PriceItem
from app.validation.versioning import _price_of, apply_versioning


# --------------------------------------------------------------------------- #
# _price_of: выбор цены для сравнения версий.
# --------------------------------------------------------------------------- #
def test_price_of_prefers_resident():
    item = PriceItem(
        price_resident_kzt=Decimal("700"),
        price_nonresident_kzt=Decimal("300"),
        price_original=Decimal("500"),
    )
    assert _price_of(item) == Decimal("700")


def test_price_of_falls_back_to_nonresident():
    item = PriceItem(
        price_resident_kzt=None,
        price_nonresident_kzt=Decimal("300"),
        price_original=Decimal("500"),
    )
    assert _price_of(item) == Decimal("300")


def test_price_of_falls_back_to_original():
    item = PriceItem(
        price_resident_kzt=None,
        price_nonresident_kzt=None,
        price_original=Decimal("500"),
    )
    assert _price_of(item) == Decimal("500")


def test_price_of_all_none():
    item = PriceItem()
    assert _price_of(item) is None


# --------------------------------------------------------------------------- #
# apply_versioning: ранние выходы.
# --------------------------------------------------------------------------- #
def test_versioning_noop_without_service_id(db, make_item):
    pid = uuid.uuid4()
    item = make_item(partner_id=pid, service_id=None, price=1000)
    info = apply_versioning(db, item)
    assert info == {
        "superseded": False,
        "anomaly": False,
        "pct_change": None,
        "duplicate": False,
    }
    assert item.is_active is True
    assert item.supersedes_item_id is None


def test_versioning_first_item_has_no_predecessor(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    item = make_item(partner_id=pid, service_id=sid, price=1000)
    info = apply_versioning(db, item)
    assert info["superseded"] is False
    assert item.is_active is True
    assert item.supersedes_item_id is None


# --------------------------------------------------------------------------- #
# apply_versioning: нормальный сценарий супердьюции.
# --------------------------------------------------------------------------- #
def test_versioning_supersedes_previous(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    old = make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(partner_id=pid, service_id=sid, price=1100, effective_date=date(2025, 1, 1))

    info = apply_versioning(db, new)

    assert info["superseded"] is True
    assert info["anomaly"] is False  # +10% < порога
    assert old.is_active is False
    assert new.is_active is True
    assert new.supersedes_item_id == old.item_id


def test_versioning_history_preserved_not_deleted(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(partner_id=pid, service_id=sid, price=1100, effective_date=date(2025, 1, 1))
    apply_versioning(db, new)
    db.commit()

    # Старая позиция по-прежнему в БД (бессрочное хранение), просто неактивна.
    all_items = db.query(PriceItem).filter_by(partner_id=pid, service_id=sid).all()
    assert len(all_items) == 2
    active = [i for i in all_items if i.is_active]
    assert len(active) == 1
    assert active[0].item_id == new.item_id


def test_versioning_isolates_other_partner(db, make_item):
    sid = uuid.uuid4()
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    other = make_item(partner_id=p2, service_id=sid, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(partner_id=p1, service_id=sid, price=2000, effective_date=date(2025, 1, 1))

    info = apply_versioning(db, new)
    # Та же услуга, но другой партнёр -> не связываются.
    assert info["superseded"] is False
    assert other.is_active is True
    assert new.supersedes_item_id is None


def test_versioning_isolates_other_service(db, make_item):
    pid = uuid.uuid4()
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    other = make_item(partner_id=pid, service_id=s2, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(partner_id=pid, service_id=s1, price=2000, effective_date=date(2025, 1, 1))

    info = apply_versioning(db, new)
    assert info["superseded"] is False
    assert other.is_active is True


# --------------------------------------------------------------------------- #
# apply_versioning: детектор аномалий (скачок цены > порога).
# --------------------------------------------------------------------------- #
def test_versioning_anomaly_on_big_jump(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(partner_id=pid, service_id=sid, price=2000, effective_date=date(2025, 1, 1))

    info = apply_versioning(db, new)

    assert info["anomaly"] is True
    assert info["pct_change"] == 1.0
    assert new.is_anomaly is True
    assert new.needs_review is True
    assert "Аномалия" in (new.verification_note or "")


def test_versioning_no_anomaly_on_small_change(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(partner_id=pid, service_id=sid, price=1100, effective_date=date(2025, 1, 1))

    info = apply_versioning(db, new)

    assert info["anomaly"] is False
    assert new.is_anomaly is False
    assert new.needs_review is False


def test_versioning_anomaly_boundary_exactly_50pct(db, make_item):
    # Ровно +50% — не аномалия (порог строгий: change > threshold).
    assert settings.anomaly_pct_threshold == 0.50
    pid, sid = uuid.uuid4(), uuid.uuid4()
    make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(partner_id=pid, service_id=sid, price=1500, effective_date=date(2025, 1, 1))

    info = apply_versioning(db, new)

    assert info["pct_change"] == 0.5
    assert info["anomaly"] is False
    assert new.is_anomaly is False


def test_versioning_anomaly_just_over_50pct(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(partner_id=pid, service_id=sid, price=1501, effective_date=date(2025, 1, 1))

    info = apply_versioning(db, new)

    assert info["pct_change"] > 0.5
    assert info["anomaly"] is True
    assert new.is_anomaly is True


def test_versioning_anomaly_note_appended_not_overwritten(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(
        partner_id=pid,
        service_id=sid,
        price=2000,
        effective_date=date(2025, 1, 1),
        verification_note="ранее проверено",
    )
    apply_versioning(db, new)
    assert new.verification_note.startswith("ранее проверено; ")
    assert "Аномалия" in new.verification_note


# --------------------------------------------------------------------------- #
# apply_versioning: порядок по дате (старая приходит после новой).
# --------------------------------------------------------------------------- #
def test_versioning_older_item_archived_not_active(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    newer = make_item(partner_id=pid, service_id=sid, price=2000, effective_date=date(2025, 1, 1))
    older = make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))

    apply_versioning(db, older)

    # Более старая по дате уходит в архив, более новая остаётся активной.
    assert older.is_active is False
    assert older.supersedes_item_id == newer.item_id
    assert newer.is_active is True


# --------------------------------------------------------------------------- #
# apply_versioning: дедупликация (раздел 9.1, та же дата).
# --------------------------------------------------------------------------- #
def test_versioning_duplicate_same_date_flagged(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    old = make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))

    info = apply_versioning(db, new)

    assert info["duplicate"] is True
    # Дубликат схлопывается: старая архивируется, новая активна.
    assert old.is_active is False
    assert new.is_active is True
    assert new.supersedes_item_id == old.item_id


def test_versioning_different_dates_not_duplicate(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2025, 1, 1))

    info = apply_versioning(db, new)
    assert info["duplicate"] is False


def test_versioning_duplicate_same_price_no_anomaly(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))

    info = apply_versioning(db, new)
    assert info["pct_change"] == 0.0
    assert info["anomaly"] is False


# --------------------------------------------------------------------------- #
# apply_versioning: идемпотентность повторного прогона.
# --------------------------------------------------------------------------- #
def test_versioning_idempotent_second_run_is_noop(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    old = make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))
    new = make_item(partner_id=pid, service_id=sid, price=2000, effective_date=date(2025, 1, 1))

    info1 = apply_versioning(db, new)
    db.commit()
    note_after_first = new.verification_note

    info2 = apply_versioning(db, new)
    db.commit()

    assert info1["superseded"] is True
    # Второй прогон: предшественник уже неактивен -> чистый no-op.
    assert info2["superseded"] is False
    assert info2["duplicate"] is False
    assert old.is_active is False
    assert new.is_active is True
    # Заметка об аномалии не дублируется при повторе.
    assert new.verification_note == note_after_first


def test_versioning_three_version_chain(db, make_item):
    pid, sid = uuid.uuid4(), uuid.uuid4()
    v1 = make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2023, 1, 1))
    v2 = make_item(partner_id=pid, service_id=sid, price=1100, effective_date=date(2024, 1, 1))
    apply_versioning(db, v2)
    db.commit()
    v3 = make_item(partner_id=pid, service_id=sid, price=1200, effective_date=date(2025, 1, 1))
    apply_versioning(db, v3)
    db.commit()

    # Активна ровно одна (последняя), цепочка supersedes ведёт назад.
    items = db.query(PriceItem).filter_by(partner_id=pid, service_id=sid).all()
    active = [i for i in items if i.is_active]
    assert len(active) == 1
    assert active[0].item_id == v3.item_id
    assert v3.supersedes_item_id == v2.item_id
    assert v2.supersedes_item_id == v1.item_id
    assert v1.is_active is False
    assert v2.is_active is False


def test_versioning_pct_change_uses_null_safe_date_order(db, make_item):
    # Без дат порядок не определён, но связывание всё равно происходит
    # (item_is_newer по умолчанию True).
    pid, sid = uuid.uuid4(), uuid.uuid4()
    old = make_item(partner_id=pid, service_id=sid, price=1000, effective_date=None)
    new = make_item(partner_id=pid, service_id=sid, price=1200, effective_date=None)

    info = apply_versioning(db, new)
    assert info["superseded"] is True
    assert old.is_active is False
    assert new.supersedes_item_id == old.item_id
