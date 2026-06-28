"""Автоматические проверки при парсинге (раздел 9.1).

Реализует всю таблицу проверок ТЗ без пропусков. Работает на ExtractedItem
до сохранения и на PriceItem после.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.config import settings
from app.models import ParseStatus
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


def is_positive_number(value: object) -> bool:
    """Цена считается валидной, только если это конечное положительное число.

    Отсекает None, bool (он же int в Python), строки, NaN и бесконечности
    до сравнения, чтобы Decimal('NaN') <= 0 не уронил проверку исключением.
    """
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, Decimal)):
        return False
    if isinstance(value, Decimal) and not value.is_finite():
        return False
    return value > 0


def _currency_code(currency: object) -> str:
    """Приводит валюту (строка или Enum Currency) к строковому коду."""
    if currency is None:
        return ""
    code = getattr(currency, "value", currency)
    return code if isinstance(code, str) else str(code)


def validate_extracted(item: ExtractedItem, effective: date | None) -> CheckResult:
    """Проверки уровня извлечённой позиции (до записи в БД)."""
    res = CheckResult()

    # Название услуги не пустое -> пропуск строки.
    if not item.service_name_raw or not item.service_name_raw.strip():
        res.flag("Пустое название услуги, строка пропущена", review=False, fatal=True)
        return res

    # Цена больше 0 и является числом. Учитываем и исходную цену в валюте,
    # чтобы позиция с одной только price_original не считалась беспрайсовой.
    present = [
        p
        for p in (item.price_resident_kzt, item.price_nonresident_kzt, item.price_original)
        if p is not None
    ]
    if not present:
        res.flag("Не распознана цена", review=True)
    else:
        for p in present:
            if not is_positive_number(p):
                res.flag(f"Цена не положительное число: {p}", review=True)

    # Цена нерезидента не меньше цены резидента (сравниваем только валидные числа).
    r, nr = item.price_resident_kzt, item.price_nonresident_kzt
    if is_positive_number(r) and is_positive_number(nr) and nr < r:
        res.flag("Цена нерезидента меньше цены резидента", review=True)

    # Дата прайса не в будущем.
    if effective and effective > date.today():
        res.flag(f"Дата прайса в будущем: {effective}", review=True)

    # Валюта не KZT -> конвертация (заложена, на этом архиве не активна).
    currency = _currency_code(item.currency_original)
    if currency and currency != "KZT":
        res.flag(f"Валюта {currency}: конвертация по курсу", review=True)

    return res


def convert_to_kzt(amount: Decimal | None, currency: object) -> Decimal | None:
    """Заглушка конвертации с фиксированным курсом (ловушка 6).

    KZT и нераспознанные валюты возвращаются без изменений. Результат
    квантуется до 2 знаков под Numeric(14, 2).
    """
    if amount is None:
        return amount
    code = _currency_code(currency)
    if not code or code == "KZT":
        return amount
    if code == "USD":
        converted = Decimal(amount) * Decimal(str(settings.fx_usd_kzt))
        return converted.quantize(Decimal("0.01"))
    return amount


def document_status(item_count: int, review_count: int) -> ParseStatus:
    """Итоговый статус документа (раздел 9.1).

    Документ без распознанных позиций -> error. Есть позиции на ревью ->
    needs_review. Иначе done. Единый источник правды для воркера.
    """
    if item_count <= 0:
        return ParseStatus.error
    if review_count > 0:
        return ParseStatus.needs_review
    return ParseStatus.done
