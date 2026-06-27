"""Контракт извлечения (паттерн Стратегия, раздел 4.1).

Новый формат = новый класс Extractor. Ядро не трогается.
Любой экстрактор возвращает ExtractionResult со списком ExtractedItem
и сырым текстом для аудита. Раскладка цен в резидент/нерезидент и
сопоставление со справочником происходят НЕ здесь, а в общих слоях
(price_parser, normalization).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class ExtractedItem:
    """Одна сырая позиция, как её увидел экстрактор.

    prices — это карта «исходная подпись тарифа -> сумма». Раскладка в
    price_resident_kzt / price_nonresident_kzt делается позже в price_parser,
    чтобы экстракторы оставались тупыми и заменяемыми.
    """

    service_name_raw: str
    service_code_source: str | None = None
    prices: dict[str, Decimal] = field(default_factory=dict)
    category: str | None = None
    source_page: int | None = None
    source_row: int | None = None
    currency_original: str = "KZT"
    # Заполняется price_parser-ом:
    price_resident_kzt: Decimal | None = None
    price_nonresident_kzt: Decimal | None = None
    price_original: Decimal | None = None
    raw_price_label: str | None = None


@dataclass
class ExtractionResult:
    items: list[ExtractedItem] = field(default_factory=list)
    raw_content: str = ""
    page_count: int = 0
    ocr_applied: bool = False
    extractor_used: str = ""
    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


class Extractor(ABC):
    """Единый интерфейс экстрактора. Реестр выбирает реализацию по формату."""

    #: человекочитаемое имя, попадает в PriceDocument.extractor_used
    name: str = "base"

    @abstractmethod
    def can_handle(self, file_path: str, file_format: str) -> bool:
        """Может ли экстрактор обработать этот файл/формат."""
        raise NotImplementedError

    @abstractmethod
    def extract(self, file_path: str) -> ExtractionResult:
        """Извлечь позиции и сырой текст из файла."""
        raise NotImplementedError
