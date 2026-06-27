"""Общий слой: парсер цен и тарифов (раздел 7.7).

Не привязан к формату. Принимает ExtractedItem с картой prices
{подпись -> сумма} и раскладывает в price_resident_kzt / price_nonresident_kzt,
сохраняя все исходные подписи в raw_price_label (ничего не теряем — ловушка 7).
"""

from __future__ import annotations

import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from app.pipeline.base import ExtractedItem

# «16 600», «16600», «9000 тг», «3 980», «14 400,00» -> Decimal
_CURRENCY_SUFFIX = re.compile(r"(тг|тенге|kzt|₸|руб|rub|\$|usd)\.?", re.IGNORECASE)
_NUM_RE = re.compile(r"\d[\d\s .,]*\d|\d")

RESIDENT_LABELS = (
    "резидент", "граждан рк", "граждане рк", "для граждан рк", "рк",
    "первичный", "первичная", "базов", "основн",
)
NONRESIDENT_LABELS = (
    "нерезидент", "не резидент", "иностран", "без гражданства",
    "дальнее зарубежье", "дальн", "повторный", "повторная",
)
INSURANCE_LABELS = ("страхов", "по страховке")
PRIMARY_REPEAT = (("первичный", "первичная"), ("повторный", "повторная"))


def parse_amount(value: str | int | float | Decimal | None) -> Decimal | None:
    """Приводит строку цены к Decimal. Убирает разрядные пробелы, валюту, мусор."""
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            d = Decimal(str(value))
            return d if d > 0 else None
        except (InvalidOperation, ValueError):
            return None

    s = _CURRENCY_SUFFIX.sub(" ", str(value))
    m = _NUM_RE.search(s)
    if not m:
        return None
    raw = m.group(0)
    # Убираем пробелы-разряды (включая неразрывные).
    raw = raw.replace(" ", "").replace(" ", "")
    # Десятичный разделитель: если есть и точка и запятая — запятая дробная.
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        # запятая как дробный разделитель только если 1-2 цифры после неё
        if re.search(r",\d{1,2}$", raw):
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")
    # «1.234.567» — точки как разрядные
    if raw.count(".") > 1:
        raw = raw.replace(".", "")
    try:
        d = Decimal(raw)
    except InvalidOperation:
        return None
    return d if d > 0 else None


def classify_label(label: str) -> str:
    """resident | nonresident | insurance | other по подписи тарифа."""
    low = (label or "").lower()
    if any(t in low for t in NONRESIDENT_LABELS):
        return "nonresident"
    if any(t in low for t in INSURANCE_LABELS):
        return "insurance"
    if any(t in low for t in RESIDENT_LABELS):
        return "resident"
    return "other"


def apply_tariffs(item: ExtractedItem) -> ExtractedItem:
    """Раскладывает карту prices в резидент/нерезидент. Базовый тариф РК ->
    резидент, дальнее зарубежье/нерезидент -> нерезидент. Полные подписи
    сохраняются в raw_price_label."""
    if not item.prices:
        return item

    parsed: dict[str, Decimal] = {}
    for label, amount in item.prices.items():
        d = amount if isinstance(amount, Decimal) else parse_amount(amount)
        if d is not None:
            parsed[label] = d
    if not parsed:
        return item

    resident: Decimal | None = None
    nonresident: Decimal | None = None
    other_vals: list[Decimal] = []

    for label, d in parsed.items():
        kind = classify_label(label)
        if kind == "resident" and resident is None:
            resident = d
        elif kind == "nonresident" and nonresident is None:
            nonresident = d
        else:
            other_vals.append(d)

    # Если явных подписей нет — первая цена резидент, вторая (если есть) нерезидент.
    ordered = list(parsed.values())
    if resident is None:
        resident = ordered[0]
    if nonresident is None and len(ordered) > 1:
        # берём максимальную из оставшихся как «дальнее зарубежье / нерезидент»
        rest = [v for v in ordered if v != resident]
        if rest:
            nonresident = max(rest)

    item.price_resident_kzt = resident
    item.price_nonresident_kzt = nonresident
    item.price_original = resident
    item.raw_price_label = " | ".join(f"{k}: {v}" for k, v in parsed.items())
    return item


def expand_primary_repeat(item: ExtractedItem) -> list[ExtractedItem]:
    """Случай первичный/повторный приём (Клиника 5): одна строка -> две услуги.
    Разворачивает в две позиции с уточнением в названии."""
    has_primary = any("первичн" in lbl.lower() for lbl in item.prices)
    has_repeat = any("повторн" in lbl.lower() for lbl in item.prices)
    if not (has_primary and has_repeat):
        return [apply_tariffs(item)]

    out: list[ExtractedItem] = []
    for kind, suffix in (("первичн", "первичный приём"), ("повторн", "повторный приём")):
        sub = deepcopy(item)
        sub.prices = {k: v for k, v in item.prices.items() if kind in k.lower()}
        if not sub.prices:
            continue
        sub.service_name_raw = f"{item.service_name_raw} ({suffix})"
        out.append(apply_tariffs(sub))
    return out or [apply_tariffs(item)]
