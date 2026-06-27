"""Тесты автоматических проверок при парсинге (раздел 9.1).

Покрывают validate_extracted (все спец-проверки таблицы ТЗ),
convert_to_kzt (конвертация валют) и pct_change (детектор скачка цены).
Все функции чистые, БД не требуется.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.config import settings
from app.pipeline.base import ExtractedItem
from app.validation.checks import CheckResult, convert_to_kzt, validate_extracted
from app.validation.versioning import pct_change


# --------------------------------------------------------------------------- #
# CheckResult: поведение агрегатора результатов.
# --------------------------------------------------------------------------- #
def test_check_result_defaults_ok():
    res = CheckResult()
    assert res.ok is True
    assert res.needs_review is False
    assert res.messages == []


def test_check_result_flag_review():
    res = CheckResult()
    res.flag("замечание")
    assert res.needs_review is True
    assert res.ok is True  # review не фатально
    assert res.messages == ["замечание"]


def test_check_result_flag_fatal_not_review():
    res = CheckResult()
    res.flag("стоп", review=False, fatal=True)
    assert res.ok is False
    assert res.needs_review is False
    assert "стоп" in res.messages


def test_check_result_flag_accumulates():
    res = CheckResult()
    res.flag("a")
    res.flag("b")
    assert res.messages == ["a", "b"]


# --------------------------------------------------------------------------- #
# validate_extracted: название услуги.
# --------------------------------------------------------------------------- #
def test_empty_name_is_fatal_and_skips():
    res = validate_extracted(ExtractedItem(service_name_raw=""), None)
    assert res.ok is False
    assert any("название" in m.lower() for m in res.messages)


def test_whitespace_name_is_fatal():
    res = validate_extracted(ExtractedItem(service_name_raw="   \t  "), None)
    assert res.ok is False


def test_empty_name_short_circuits_other_checks():
    # При пустом имени остальные проверки не выполняются: ровно одно сообщение.
    res = validate_extracted(
        ExtractedItem(service_name_raw="", price_resident_kzt=Decimal("-5")), None
    )
    assert res.ok is False
    assert len(res.messages) == 1


def test_valid_item_passes_cleanly():
    res = validate_extracted(
        ExtractedItem(
            service_name_raw="Общий анализ крови",
            price_resident_kzt=Decimal("1780"),
        ),
        date(2024, 1, 1),
    )
    assert res.ok is True
    assert res.needs_review is False
    assert res.messages == []


# --------------------------------------------------------------------------- #
# validate_extracted: цена.
# --------------------------------------------------------------------------- #
def test_missing_price_flags_review():
    res = validate_extracted(ExtractedItem(service_name_raw="Услуга"), None)
    assert res.ok is True
    assert res.needs_review is True
    assert any("цена" in m.lower() for m in res.messages)


def test_zero_price_flags_review():
    res = validate_extracted(
        ExtractedItem(service_name_raw="Услуга", price_resident_kzt=Decimal("0")), None
    )
    assert res.needs_review is True
    assert any("положительное" in m.lower() for m in res.messages)


def test_negative_price_flags_review():
    res = validate_extracted(
        ExtractedItem(service_name_raw="Услуга", price_resident_kzt=Decimal("-100")),
        None,
    )
    assert res.needs_review is True
    assert res.ok is True  # не фатально, только на ревью


def test_positive_price_passes():
    res = validate_extracted(
        ExtractedItem(service_name_raw="Услуга", price_resident_kzt=Decimal("0.01")),
        None,
    )
    assert res.needs_review is False


def test_nonresident_price_validated_too():
    # Цена резидента валидна, нерезидента нулевая -> на ревью.
    res = validate_extracted(
        ExtractedItem(
            service_name_raw="Услуга",
            price_resident_kzt=Decimal("100"),
            price_nonresident_kzt=Decimal("0"),
        ),
        None,
    )
    assert res.needs_review is True


# --------------------------------------------------------------------------- #
# validate_extracted: соотношение резидент/нерезидент.
# --------------------------------------------------------------------------- #
def test_nonresident_below_resident_flags_review():
    res = validate_extracted(
        ExtractedItem(
            service_name_raw="Услуга",
            price_resident_kzt=Decimal("200"),
            price_nonresident_kzt=Decimal("100"),
        ),
        None,
    )
    assert res.needs_review is True
    assert any("нерезидент" in m.lower() for m in res.messages)


def test_nonresident_equal_resident_ok():
    res = validate_extracted(
        ExtractedItem(
            service_name_raw="Услуга",
            price_resident_kzt=Decimal("200"),
            price_nonresident_kzt=Decimal("200"),
        ),
        None,
    )
    assert res.needs_review is False


def test_nonresident_above_resident_ok():
    res = validate_extracted(
        ExtractedItem(
            service_name_raw="Услуга",
            price_resident_kzt=Decimal("200"),
            price_nonresident_kzt=Decimal("300"),
        ),
        None,
    )
    assert res.needs_review is False


# --------------------------------------------------------------------------- #
# validate_extracted: дата прайса.
# --------------------------------------------------------------------------- #
def test_future_date_flags_review():
    future = date.today() + timedelta(days=30)
    res = validate_extracted(
        ExtractedItem(service_name_raw="Услуга", price_resident_kzt=Decimal("100")),
        future,
    )
    assert res.needs_review is True
    assert any("будущ" in m.lower() for m in res.messages)


def test_today_date_not_future():
    res = validate_extracted(
        ExtractedItem(service_name_raw="Услуга", price_resident_kzt=Decimal("100")),
        date.today(),
    )
    assert res.needs_review is False


def test_past_date_ok():
    res = validate_extracted(
        ExtractedItem(service_name_raw="Услуга", price_resident_kzt=Decimal("100")),
        date(2020, 1, 1),
    )
    assert res.needs_review is False


def test_none_date_ok():
    res = validate_extracted(
        ExtractedItem(service_name_raw="Услуга", price_resident_kzt=Decimal("100")),
        None,
    )
    assert res.needs_review is False


# --------------------------------------------------------------------------- #
# validate_extracted: валюта.
# --------------------------------------------------------------------------- #
def test_kzt_currency_no_flag():
    res = validate_extracted(
        ExtractedItem(
            service_name_raw="Услуга",
            price_resident_kzt=Decimal("100"),
            currency_original="KZT",
        ),
        None,
    )
    assert res.needs_review is False


def test_non_kzt_currency_flags_review():
    res = validate_extracted(
        ExtractedItem(
            service_name_raw="Услуга",
            price_resident_kzt=Decimal("100"),
            currency_original="USD",
        ),
        None,
    )
    assert res.needs_review is True
    assert any("USD" in m for m in res.messages)


def test_multiple_issues_accumulate_messages():
    future = date.today() + timedelta(days=5)
    res = validate_extracted(
        ExtractedItem(
            service_name_raw="Услуга",
            price_resident_kzt=Decimal("200"),
            price_nonresident_kzt=Decimal("100"),
            currency_original="USD",
        ),
        future,
    )
    assert res.needs_review is True
    # нерезидент<резидент + будущая дата + валюта = минимум 3 замечания
    assert len(res.messages) >= 3


# --------------------------------------------------------------------------- #
# convert_to_kzt: конвертация валют (ловушка 6).
# --------------------------------------------------------------------------- #
def test_convert_kzt_passthrough():
    assert convert_to_kzt(Decimal("1000"), "KZT") == Decimal("1000")


def test_convert_none_amount():
    assert convert_to_kzt(None, "USD") is None
    assert convert_to_kzt(None, "KZT") is None


def test_convert_usd_uses_fx_rate():
    result = convert_to_kzt(Decimal("100"), "USD")
    expected = Decimal("100") * Decimal(str(settings.fx_usd_kzt))
    assert result == expected
    assert isinstance(result, Decimal)


def test_convert_unknown_currency_passthrough():
    # Неизвестная валюта (нет курса) -> сумма без изменений.
    assert convert_to_kzt(Decimal("100"), "RUB") == Decimal("100")
    assert convert_to_kzt(Decimal("100"), "EUR") == Decimal("100")


def test_convert_usd_zero():
    assert convert_to_kzt(Decimal("0"), "USD") == Decimal("0")


# --------------------------------------------------------------------------- #
# pct_change: детектор аномалий (скачок цены).
# --------------------------------------------------------------------------- #
def test_pct_change_increase():
    assert pct_change(Decimal("1000"), Decimal("2000")) == 1.0


def test_pct_change_decrease_is_absolute():
    # Падение цены вдвое тоже 50% по модулю.
    assert pct_change(Decimal("1000"), Decimal("500")) == 0.5


def test_pct_change_exactly_threshold():
    # Ровно +50%: пограничный случай детектора.
    change = pct_change(Decimal("1000"), Decimal("1500"))
    assert change == 0.5
    assert change <= settings.anomaly_pct_threshold  # не аномалия (строгое >)


def test_pct_change_just_over_threshold():
    change = pct_change(Decimal("1000"), Decimal("1501"))
    assert change > settings.anomaly_pct_threshold


def test_pct_change_small_change():
    assert pct_change(Decimal("1000"), Decimal("1010")) == 0.01


def test_pct_change_zero_old_returns_none():
    assert pct_change(Decimal("0"), Decimal("100")) is None


def test_pct_change_none_inputs_return_none():
    assert pct_change(None, Decimal("100")) is None
    assert pct_change(Decimal("100"), None) is None
    assert pct_change(None, None) is None


def test_pct_change_no_change():
    assert pct_change(Decimal("1000"), Decimal("1000")) == 0.0
