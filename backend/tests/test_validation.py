"""Тесты автоматических проверок прайса (раздел 9.1).

Покрывают всю таблицу проверок ТЗ: цена > 0 и число, нерезидент не дешевле
резидента, пустое имя в пропуск, дата не в будущем, конвертация валюты и
итоговый статус документа без данных.
"""

from datetime import date, timedelta
from decimal import Decimal

from app.models import Currency, ParseStatus
from app.pipeline.base import ExtractedItem
from app.validation.checks import (
    convert_to_kzt,
    document_status,
    is_positive_number,
    validate_extracted,
)


def _item(**kw) -> ExtractedItem:
    base = {"service_name_raw": "Консультация врача"}
    base.update(kw)
    return ExtractedItem(**base)


# --------------------------------------------------------------------------- #
# Пустое имя -> пропуск строки (fatal).
# --------------------------------------------------------------------------- #
def test_empty_name_is_skipped():
    res = validate_extracted(_item(service_name_raw=""), None)
    assert res.ok is False
    assert "пропущена" in res.messages[0].lower()


def test_whitespace_name_is_skipped():
    res = validate_extracted(_item(service_name_raw="   \t  "), None)
    assert res.ok is False


def test_valid_item_passes_clean():
    res = validate_extracted(
        _item(price_resident_kzt=Decimal("5000"), price_nonresident_kzt=Decimal("8000")),
        date.today(),
    )
    assert res.ok is True
    assert res.needs_review is False
    assert res.messages == []


# --------------------------------------------------------------------------- #
# Цена больше 0 и является числом.
# --------------------------------------------------------------------------- #
def test_zero_price_flagged():
    res = validate_extracted(_item(price_resident_kzt=Decimal("0")), None)
    assert res.needs_review is True
    assert any("положительное" in m for m in res.messages)


def test_negative_price_flagged():
    res = validate_extracted(_item(price_resident_kzt=Decimal("-100")), None)
    assert any("положительное" in m for m in res.messages)


def test_nan_price_does_not_crash_and_flags():
    res = validate_extracted(_item(price_resident_kzt=Decimal("NaN")), None)
    assert res.needs_review is True
    assert any("положительное" in m for m in res.messages)


def test_no_price_flagged():
    res = validate_extracted(_item(), None)
    assert any("Не распознана цена" in m for m in res.messages)
    assert res.needs_review is True


def test_price_original_only_is_not_treated_as_missing():
    res = validate_extracted(_item(price_original=Decimal("300")), None)
    assert not any("Не распознана цена" in m for m in res.messages)


# --------------------------------------------------------------------------- #
# Цена нерезидента не меньше цены резидента.
# --------------------------------------------------------------------------- #
def test_nonresident_below_resident_flagged():
    res = validate_extracted(
        _item(price_resident_kzt=Decimal("8000"), price_nonresident_kzt=Decimal("5000")),
        None,
    )
    assert any("нерезидента меньше" in m for m in res.messages)


def test_nonresident_equal_resident_ok():
    res = validate_extracted(
        _item(price_resident_kzt=Decimal("5000"), price_nonresident_kzt=Decimal("5000")),
        None,
    )
    assert not any("нерезидента меньше" in m for m in res.messages)


def test_nonresident_above_resident_ok():
    res = validate_extracted(
        _item(price_resident_kzt=Decimal("5000"), price_nonresident_kzt=Decimal("9000")),
        None,
    )
    assert not any("нерезидента меньше" in m for m in res.messages)


# --------------------------------------------------------------------------- #
# Дата прайса не в будущем.
# --------------------------------------------------------------------------- #
def test_future_date_flagged():
    future = date.today() + timedelta(days=30)
    res = validate_extracted(_item(price_resident_kzt=Decimal("5000")), future)
    assert any("будущем" in m for m in res.messages)


def test_today_date_ok():
    res = validate_extracted(_item(price_resident_kzt=Decimal("5000")), date.today())
    assert not any("будущем" in m for m in res.messages)


def test_past_date_ok():
    past = date.today() - timedelta(days=365)
    res = validate_extracted(_item(price_resident_kzt=Decimal("5000")), past)
    assert not any("будущем" in m for m in res.messages)


# --------------------------------------------------------------------------- #
# Валюта не KZT -> сигнал о конвертации.
# --------------------------------------------------------------------------- #
def test_foreign_currency_flagged():
    res = validate_extracted(
        _item(price_resident_kzt=Decimal("100"), currency_original="USD"), None
    )
    assert any("Валюта USD" in m for m in res.messages)


def test_kzt_currency_not_flagged():
    res = validate_extracted(
        _item(price_resident_kzt=Decimal("100"), currency_original="KZT"), None
    )
    assert not any("Валюта" in m for m in res.messages)


def test_multiple_issues_accumulate():
    future = date.today() + timedelta(days=10)
    res = validate_extracted(
        _item(
            price_resident_kzt=Decimal("8000"),
            price_nonresident_kzt=Decimal("5000"),
            currency_original="USD",
        ),
        future,
    )
    assert len(res.messages) >= 3
    assert res.needs_review is True
    assert res.ok is True  # ни одна из этих проверок не fatal


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
# Конвертация валюты (раздел 9.1, ловушка 6).
# --------------------------------------------------------------------------- #
def test_convert_none_returns_none():
    assert convert_to_kzt(None, "USD") is None


def test_convert_kzt_unchanged():
    assert convert_to_kzt(Decimal("100"), "KZT") == Decimal("100")


def test_convert_usd_uses_rate_and_quantizes():
    out = convert_to_kzt(Decimal("100"), "USD")
    assert out == Decimal("47500.00")
    assert out.as_tuple().exponent == -2  # ровно 2 знака под Numeric(14, 2)


def test_convert_currency_enum_path():
    assert convert_to_kzt(Decimal("100"), Currency.USD) == Decimal("47500.00")
    assert convert_to_kzt(Decimal("100"), Currency.KZT) == Decimal("100")


def test_convert_unknown_currency_passthrough():
    # RUB без курса -> возвращаем без изменений (заглушка), не падаем.
    assert convert_to_kzt(Decimal("100"), "RUB") == Decimal("100")
    assert convert_to_kzt(Decimal("100"), None) == Decimal("100")


# --------------------------------------------------------------------------- #
# Документ без данных -> статус error.
# --------------------------------------------------------------------------- #
def test_document_status_no_items_is_error():
    assert document_status(0, 0) is ParseStatus.error
    assert document_status(-1, 0) is ParseStatus.error


def test_document_status_with_review():
    assert document_status(10, 3) is ParseStatus.needs_review


def test_document_status_clean_is_done():
    assert document_status(10, 0) is ParseStatus.done
