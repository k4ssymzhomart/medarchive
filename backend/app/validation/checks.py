"""Автоматические проверки при парсинге (раздел 9.1).

Реализует всю таблицу проверок ТЗ без пропусков. Работает на ExtractedItem
до сохранения и на PriceItem после.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.config import settings
from app.pipeline.base import ExtractedItem


@dataclass
class CheckResult:
    ok: bool = True               # можно ли вообще сохранять строку
    needs_review: bool = False
    messages: list[str] = field(default_factory=list)

    def flag(self, msg: str, *, review: bool = True, fatal: bool = False) -> None:
        self.messages.append(msg)
        if review:
            self.needs_review = True
        if fatal:
            self.ok = False


def validate_extracted(item: ExtractedItem, effective: date | None) -> CheckResult:
    """Проверки уровня извлечённой позиции (до записи в БД)."""
    res = CheckResult()

    # Название услуги не пустое -> пропуск строки.
    if not item.service_name_raw or not item.service_name_raw.strip():
        res.flag("Пустое название услуги, строка пропущена", review=False, fatal=True)
        return res

    # Цена больше 0 и является числом.
    prices = [p for p in (item.price_resident_kzt, item.price_nonresident_kzt) if p is not None]
    if not prices:
        res.flag("Не распознана цена", review=True)
    else:
        for p in prices:
            if not isinstance(p, Decimal) or p <= 0:
                res.flag(f"Цена не положительное число: {p}", review=True)

    # Цена нерезидента не меньше цены резидента.
    r, nr = item.price_resident_kzt, item.price_nonresident_kzt
    if r is not None and nr is not None and nr < r:
        res.flag("Цена нерезидента меньше цены резидента", review=True)

    # Дата прайса не в будущем.
    if effective and effective > date.today():
        res.flag(f"Дата прайса в будущем: {effective}", review=True)

    # Валюта не KZT -> конвертация (заложена, на этом архиве не активна).
    if item.currency_original and item.currency_original != "KZT":
        res.flag(f"Валюта {item.currency_original}: конвертация по курсу", review=True)

    return res


def convert_to_kzt(amount: Decimal | None, currency: str) -> Decimal | None:
    """Заглушка конвертации с фиксированным курсом (ловушка 6)."""
    if amount is None or currency == "KZT":
        return amount
    if currency == "USD":
        return amount * Decimal(str(settings.fx_usd_kzt))
    return amount
