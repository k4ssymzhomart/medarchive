"""Экстрактор текстового слоя PDF (раздел 7.2, ловушка 2).

Для чистых текстовых PDF архива (Клиника 1 — 85 страниц, Клиника 2 2025,
Клиника 4, Клиника 5). extract_tables во всех этих PDF возвращает ноль таблиц,
поэтому разметку держим на координатах слов: extract_words -> Word -> строки
(group_rows) -> колонки (cluster_columns / assign_to_columns) -> семантика
(map_columns). Цены кладём в карту prices по подписи колонки из заголовка;
раскладка в резидент/нерезидент делается позже в price_parser.

Страницы обрабатываем потоково (page за page), не держа весь документ в памяти,
чтобы 85 страничные прайсы не съедали лишнего. Никогда не падаем на одной плохой
строке — копим проблемы через result.warn().
"""

from __future__ import annotations

from decimal import Decimal

import pdfplumber

from app.pipeline.base import ExtractedItem, ExtractionResult, Extractor
from app.pipeline.columns import (
    ColumnMap,
    Row,
    Word,
    analyze_table,
    assign_to_columns,
    group_rows,
)
from app.pipeline.price_parser import parse_amount

# Строки итогов/подытогов пропускаем — это не услуги.
_TOTAL_MARKERS = ("итого", "всего", "подытог", "сумма по разделу", "итог")


class PdfTextExtractor(Extractor):
    """Извлекает позиции из PDF с валидным текстовым слоем по геометрии слов."""

    name = "pdf_text"

    def can_handle(self, file_path: str, file_format: str) -> bool:
        """Берём только чистый текстовый PDF (scan_pdf уходит другому экстрактору)."""
        # Ленивый импорт: app.models тянет тяжёлые БД зависимости, не нужные на старте.
        from app.models import FileFormat

        return file_format == FileFormat.pdf.value

    def extract(self, file_path: str) -> ExtractionResult:
        result = ExtractionResult(extractor_used=self.name)
        raw_pages: list[str] = []
        category: str | None = None  # переносим текущий раздел между строками и страницами

        try:
            pdf = pdfplumber.open(file_path)
        except Exception as exc:  # noqa: BLE001 — файл может быть битым, не валимся
            result.warn(f"Не удалось открыть PDF: {exc}")
            return result

        with pdf:
            result.page_count = len(pdf.pages)
            for page_number, page in enumerate(pdf.pages, start=1):
                try:
                    # Текст страницы — для аудита raw_content.
                    page_text = page.extract_text() or ""
                    raw_pages.append(page_text)

                    words = self._extract_words(page)
                    if not words:
                        continue

                    rows = group_rows(words)
                    # Границы колонок по плотности строк данных (устойчиво к
                    # многострочным шапкам), роли колонок из заголовка или по содержимому.
                    bounds, cmap, header_idx = analyze_table(rows)
                    if not bounds or not cmap.price_idxs:
                        result.warn(f"Страница {page_number}: структура таблицы не распознана")
                        continue

                    data_rows = rows[header_idx + 1:] if header_idx >= 0 else rows
                    category = self._consume_rows(
                        data_rows, cmap, bounds, page_number, category, result
                    )
                except Exception as exc:  # noqa: BLE001 — одна страница не валит весь файл
                    result.warn(f"Страница {page_number}: ошибка разбора ({exc})")

        result.raw_content = "\n".join(raw_pages)
        result.ocr_applied = False
        return result

    # --- геометрия --------------------------------------------------------

    @staticmethod
    def _extract_words(page) -> list[Word]:
        """page.extract_words -> наши Word с координатами в точках PDF."""
        words: list[Word] = []
        try:
            raw_words = page.extract_words(x_tolerance=2, keep_blank_chars=False)
        except Exception:  # noqa: BLE001
            return words
        for w in raw_words:
            text = (w.get("text") or "").strip()
            if not text:
                continue
            try:
                words.append(
                    Word(
                        text=text,
                        x0=float(w["x0"]),
                        x1=float(w["x1"]),
                        top=float(w["top"]),
                        bottom=float(w["bottom"]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return words

    # --- разбор строк -----------------------------------------------------

    def _consume_rows(
        self,
        data_rows: list[Row],
        cmap: ColumnMap,
        bounds: list[float],
        page_number: int,
        category: str | None,
        result: ExtractionResult,
    ) -> str | None:
        """Проходит строки ниже заголовка, собирает позиции, тащит категорию вперёд."""
        for row in data_rows:
            try:
                item, new_category = self._parse_row(row, cmap, bounds, page_number, category)
                if new_category is not None:
                    category = new_category
                    continue
                if item is not None:
                    result.items.append(item)
            except Exception as exc:  # noqa: BLE001 — плохая строка не валит страницу
                result.warn(f"Страница {page_number}: строка пропущена ({exc})")
        return category

    def _parse_row(
        self,
        row: Row,
        cmap: ColumnMap,
        bounds: list[float],
        page_number: int,
        category: str | None,
    ) -> tuple[ExtractedItem | None, str | None]:
        """Разбирает одну строку.

        Возвращает (item, new_category):
        - (None, "РАЗДЕЛ") — строка раздела/категории (только текст, ни одной цены);
        - (item, None)     — обычная позиция;
        - (None, None)     — мусор (заголовок-повтор, итог, пустая строка).
        """
        cells = assign_to_columns(row, bounds)
        if not any(c.strip() for c in cells):
            return None, None

        # Парсим цены по тарифным колонкам заголовка.
        prices: dict[str, Decimal] = {}
        for idx in cmap.price_idxs:
            if idx >= len(cells):
                continue
            amount = parse_amount(cells[idx])
            if amount is not None:
                label = cmap.labels.get(idx) or f"Цена {idx}"
                prices[label] = amount

        # Имя: явная колонка name_idx, иначе самая широкая текстовая ячейка
        # (нечисловая, без кода).
        name = self._read_name(cells, cmap)
        low_name = name.lower().strip()

        # Итоги/подытоги отбрасываем.
        if any(m in low_name for m in _TOTAL_MARKERS):
            return None, None

        # Повтор строки заголовка на странице — отбрасываем.
        if not prices and self._looks_like_header(cells, cmap):
            return None, None

        # Строка раздела: есть текст, но ни одна цена не распарсилась.
        if not prices:
            if self._is_section_row(cells, cmap):
                section = (name or row.text()).strip()
                return None, section or None
            # Текст без цены и не похож на раздел — пропускаем как мусор.
            return None, None

        if not name:
            # Цены есть, имени нет — берём весь текст строки, чтобы ничего не терять.
            name = row.text().strip()
        if not name:
            return None, None

        code: str | None = None
        if cmap.code_idx is not None and cmap.code_idx < len(cells):
            code = cells[cmap.code_idx].strip() or None

        item = ExtractedItem(
            service_name_raw=name,
            service_code_source=code,
            prices=prices,
            category=category,
            source_page=page_number,
            source_row=int(round(row.top)),
        )
        return item, None

    @staticmethod
    def _read_name(cells: list[str], cmap: ColumnMap) -> str:
        """Имя услуги: name_idx, иначе самая широкая текстовая (нечисловая) ячейка."""
        if cmap.name_idx is not None and cmap.name_idx < len(cells):
            explicit = cells[cmap.name_idx].strip()
            if explicit:
                return explicit
        # Фолбэк: самая длинная ячейка, которая не код и не чистая цена.
        best = ""
        for idx, cell in enumerate(cells):
            text = cell.strip()
            if not text:
                continue
            if idx == cmap.code_idx:
                continue
            if idx in cmap.price_idxs and parse_amount(text) is not None:
                continue
            if parse_amount(text) is not None and len(text) <= 12:
                continue  # короткая чисто числовая ячейка — это не название
            if len(text) > len(best):
                best = text
        return best

    @staticmethod
    def _is_section_row(cells: list[str], cmap: ColumnMap) -> bool:
        """Строка раздела: ровно одна непустая ячейка, она текстовая, без цен."""
        from app.pipeline.columns import HEADER_ANCHORS

        non_empty = [c.strip() for c in cells if c.strip()]
        if len(non_empty) != 1:
            return False
        only = non_empty[0]
        if parse_amount(only) is not None:
            return False
        # Одинокое якорное слово шапки («Код», «Цена») это не раздел.
        if only.lower() in HEADER_ANCHORS or len(only) < 4:
            return False
        # Должна быть осмысленная подпись (буквы), а не одинокий код/символ.
        return any(ch.isalpha() for ch in only)

    @staticmethod
    def _looks_like_header(cells: list[str], cmap: ColumnMap) -> bool:
        """Повтор шапки на странице: ячейки совпадают с подписями колонок."""
        if not cmap.labels:
            return False
        hits = 0
        for idx, label in cmap.labels.items():
            if idx < len(cells) and label and cells[idx].strip().lower() == label.lower():
                hits += 1
        return hits >= 2
