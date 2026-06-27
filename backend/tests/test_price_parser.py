"""Тесты парсера цен и раскладки тарифов (раздел 7.7)."""

from decimal import Decimal

from app.pipeline.base import ExtractedItem
from app.pipeline.price_parser import (
    apply_tariffs,
    classify_label,
    expand_primary_repeat,
    parse_amount,
)


def test_parse_amount_basic():
    assert parse_amount("16 600") == Decimal("16600")
    assert parse_amount("16600") == Decimal("16600")
    assert parse_amount("9000 тг") == Decimal("9000")
    assert parse_amount("3 980") == Decimal("3980")
    assert parse_amount("14 400,00") == Decimal("14400.00")
    assert parse_amount("1 234 567") == Decimal("1234567")


def test_parse_amount_garbage():
    assert parse_amount("") is None
    assert parse_amount(None) is None
    assert parse_amount("бесплатно") is None
    assert parse_amount("0") is None  # цена должна быть > 0


def test_parse_amount_nbsp():
    assert parse_amount("16 600 тенге") == Decimal("16600")


def test_classify_label():
    assert classify_label("Цена для резидентов") == "resident"
    assert classify_label("Цена для нерезидентов") == "nonresident"
    assert classify_label("дальнее зарубежье") == "nonresident"
    assert classify_label("страховые компании") == "insurance"
    assert classify_label("Стоимость") == "other"


def test_apply_tariffs_two_columns():
    item = ExtractedItem(
        service_name_raw="Консультация врача",
        prices={"Резидент РК": Decimal("5000"), "Нерезидент": Decimal("8000")},
    )
    apply_tariffs(item)
    assert item.price_resident_kzt == Decimal("5000")
    assert item.price_nonresident_kzt == Decimal("8000")
    assert "Резидент" in item.raw_price_label


def test_apply_tariffs_three_tariffs_keeps_labels():
    item = ExtractedItem(
        service_name_raw="Анализ",
        prices={
            "РК": Decimal("1000"),
            "СНГ": Decimal("1500"),
            "дальнее зарубежье": Decimal("2000"),
        },
    )
    apply_tariffs(item)
    assert item.price_resident_kzt == Decimal("1000")
    assert item.price_nonresident_kzt == Decimal("2000")  # дальнее зарубежье
    # ничего не теряем
    assert "СНГ" in item.raw_price_label


def test_expand_primary_repeat():
    item = ExtractedItem(
        service_name_raw="Приём терапевта",
        prices={"первичный": Decimal("9000"), "повторный": Decimal("6000")},
    )
    out = expand_primary_repeat(item)
    assert len(out) == 2
    names = {i.service_name_raw for i in out}
    assert any("первичный" in n for n in names)
    assert any("повторный" in n for n in names)
