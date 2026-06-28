"""Закалка слоя валидации (issue #22): прод-часть закрытого PR #16 поверх
влитых тестов #20.

Покрывает то, что добавила/исправила закалка и чего не было в #20:
- is_positive_number: строгое «конечное число > 0» (bool, NaN, Infinity отсечены);
- price_original как самостоятельная цена (не «беспрайсовая» позиция);
- convert_to_kzt: путь через Enum Currency и квантование до 2 знаков;
- document_status: единый источник правды о статусе документа;
- _price_of: Decimal('0') — заполненное поле, а не пропуск;
- pct_change: нечисловые (NaN/Infinity) -> None;
- apply_versioning: флаги аномалии садятся на активную свежую версию,
  а не на входящую более старую (архивную).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.models import Currency, ParseStatus
from app.pipeline.base import ExtractedItem
from app.validation.checks import (
    convert_to_kzt,
    document_status,
    is_positive_number,
    validate_extracted,
)
from app.validation.versioning import _price_of, apply_versioning, pct_change


# --------------------------------------------------------------------------- #
# is_positive_number — строгое определение «число > 0».
# --------------------------------------------------------------------------- #
def test_is_positive_number_accepts_positive():
    assert is_positive_number(Decimal("1")) is True
    assert is_positive_number(Decimal("0.01")) is True
    assert is_positive_number(100) is True


def test_is_positive_number_rejects_nonpositive_and_nonnumbers():
    assert is_positive_number(Decimal("0")) is False
    assert is_positive_number(Decimal("-1")) is False
    assert is_positive_number(None) is False
    assert is_positive_number("100") is False
    assert is_positive_number(True) is False  # bool — не цена
    assert is_positive_number(False) is False
    assert is_positive_number(Decimal("NaN")) is False
    assert is_positive_number(Decimal("Infinity")) is False


# --------------------------------------------------------------------------- #
# validate_extracted — закалённые ветки цены.
# --------------------------------------------------------------------------- #
def test_nan_price_does_not_crash_and_flags():
    # Decimal('NaN') <= 0 кинул бы InvalidOperation без is_positive_number.
    res = validate_extracted(
        ExtractedItem(service_name_raw="Услуга", price_resident_kzt=Decimal("NaN")), None
    )
    assert res.needs_review is True
    assert any("положительное" in m for m in res.messages)


def test_price_original_only_is_not_treated_as_missing():
    res = validate_extracted(
        ExtractedItem(service_name_raw="Услуга", price_original=Decimal("300")), None
    )
    assert not any("Не распознана цена" in m for m in res.messages)


def test_nonresident_compare_skips_when_one_side_invalid():
    # nr=NaN: сравнение нерезидент<резидент пропускается, но NaN всё равно
    # ловится проверкой «не положительное число».
    res = validate_extracted(
        ExtractedItem(
            service_name_raw="Услуга",
            price_resident_kzt=Decimal("100"),
            price_nonresident_kzt=Decimal("NaN"),
        ),
        None,
    )
    assert not any("нерезидента меньше" in m for m in res.messages)
    assert any("положительное" in m for m in res.messages)


# --------------------------------------------------------------------------- #
# convert_to_kzt — поддержка Enum и квантование.
# --------------------------------------------------------------------------- #
def test_convert_currency_enum_path():
    assert convert_to_kzt(Decimal("100"), Currency.USD) == Decimal("47500.00")
    assert convert_to_kzt(Decimal("100"), Currency.KZT) == Decimal("100")


def test_convert_usd_quantizes_to_two_places():
    out = convert_to_kzt(Decimal("100"), "USD")
    assert out == Decimal("47500.00")
    assert out.as_tuple().exponent == -2  # ровно 2 знака под Numeric(14, 2)


def test_convert_none_currency_passthrough():
    assert convert_to_kzt(Decimal("100"), None) == Decimal("100")


# --------------------------------------------------------------------------- #
# document_status — единый источник правды о статусе документа.
# --------------------------------------------------------------------------- #
def test_document_status_no_items_is_error():
    assert document_status(0, 0) is ParseStatus.error
    assert document_status(-1, 0) is ParseStatus.error


def test_document_status_with_review_is_needs_review():
    assert document_status(10, 3) is ParseStatus.needs_review


def test_document_status_clean_is_done():
    assert document_status(10, 0) is ParseStatus.done


# --------------------------------------------------------------------------- #
# _price_of / pct_change — закалка выбора цены и детектора скачка.
# --------------------------------------------------------------------------- #
def test_price_of_returns_zero_not_skip():
    from app.models import PriceItem

    # Decimal('0') ложен, но это заполненное поле — ``or`` ошибочно бы его пропустил.
    item = PriceItem(price_resident_kzt=Decimal("0"), price_nonresident_kzt=Decimal("200"))
    assert _price_of(item) == Decimal("0")


def test_pct_change_non_finite_returns_none():
    assert pct_change(Decimal("NaN"), Decimal("100")) is None
    assert pct_change(Decimal("100"), Decimal("Infinity")) is None


# --------------------------------------------------------------------------- #
# apply_versioning — флаги аномалии на активной свежей версии.
# --------------------------------------------------------------------------- #
def test_anomaly_flags_land_on_active_when_incoming_is_older(db, make_item):
    # Сначала есть свежая активная версия 2025/2000. Приходит более старая
    # 2024/1000: входящую архивируем, но скачок +100% обязан пометить именно
    # активную свежую версию (её видит оператор), а не архивную входящую.
    pid, sid = uuid.uuid4(), uuid.uuid4()
    newer = make_item(partner_id=pid, service_id=sid, price=2000, effective_date=date(2025, 1, 1))
    older = make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))

    info = apply_versioning(db, older)

    assert info["anomaly"] is True
    assert info["pct_change"] == 1.0  # база — более старая входящая (1000)
    # Флаги — на активной свежей версии.
    assert newer.is_active is True
    assert newer.is_anomaly is True
    assert newer.needs_review is True
    assert "Аномалия" in (newer.verification_note or "")
    # Входящая старая ушла в архив и аномалией НЕ помечена.
    assert older.is_active is False
    assert not older.is_anomaly
    assert "Аномалия" not in (older.verification_note or "")


def test_anomaly_note_idempotent_on_older_incoming_rerun(db, make_item):
    # prev остаётся активной в этой ветке, поэтому повторный приход той же более
    # старой позиции не должен дублировать заметку об аномалии на активной строке.
    pid, sid = uuid.uuid4(), uuid.uuid4()
    newer = make_item(partner_id=pid, service_id=sid, price=2000, effective_date=date(2025, 1, 1))
    older = make_item(partner_id=pid, service_id=sid, price=1000, effective_date=date(2024, 1, 1))

    apply_versioning(db, older)
    note_after_first = newer.verification_note
    apply_versioning(db, older)  # повторный прогон

    assert newer.verification_note == note_after_first
    assert newer.verification_note.count("Аномалия") == 1
