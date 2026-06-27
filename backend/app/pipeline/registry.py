"""Реестр экстракторов. Выбор реализации по формату (раздел 4.1).

Добавление нового формата = регистрация нового класса здесь. Ядро pipeline
(tasks/document_service) обращается только к get_extractor().
"""

from __future__ import annotations

from app.pipeline.base import Extractor


class ExtractorRegistry:
    def __init__(self) -> None:
        self._extractors: list[Extractor] = []

    def register(self, extractor: Extractor) -> Extractor:
        self._extractors.append(extractor)
        return extractor

    def get_extractor(self, file_path: str, file_format: str) -> Extractor:
        for extractor in self._extractors:
            if extractor.can_handle(file_path, file_format):
                return extractor
        raise LookupError(f"Нет экстрактора для формата {file_format!r} ({file_path})")

    @property
    def names(self) -> list[str]:
        return [e.name for e in self._extractors]


registry = ExtractorRegistry()


def build_default_registry() -> ExtractorRegistry:
    """Регистрирует все доступные экстракторы. Порядок = приоритет."""
    # Импорт внутри функции, чтобы избежать тяжёлых зависимостей при старте API.
    from app.pipeline.extractors.docx_extractor import DocxExtractor
    from app.pipeline.extractors.pdf_scan import PdfScanExtractor
    from app.pipeline.extractors.pdf_text import PdfTextExtractor
    from app.pipeline.extractors.xls_extractor import XlsExtractor
    from app.pipeline.extractors.xlsx_extractor import XlsxExtractor

    registry._extractors.clear()
    registry.register(PdfScanExtractor())  # scan_pdf проверяется раньше pdf
    registry.register(PdfTextExtractor())
    registry.register(DocxExtractor())
    registry.register(XlsxExtractor())
    registry.register(XlsExtractor())
    return registry
