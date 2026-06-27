"""Экстрактор сканированных / битых-OCR PDF (раздел 7.3).

Это наш дифференциатор по критерию 30 процентов. Клиника 2 и Клиника 3
2026 года поставляются как PDF с битым встроенным OCR-слоем
(«Прейскурант иен», «yc.iv!»). pdfplumber честно отдаёт этот мусорный
текст, поэтому мы постранично проверяем качество слоя (page_needs_ocr) и,
если страница битая или пустая, переOCR-иваем её через Tesseract
(ocr_page_words) — координаты слов уже масштабированы в точки PDF, поэтому
дальше работает ТА ЖЕ геометрия колонок, что и для чистого текстового PDF.

Во всех PDF архива extract_tables возвращает ноль таблиц — опираемся
исключительно на координаты слов (раздел 7.2).
"""

from __future__ import annotations

import pdfplumber

from app.pipeline.base import ExtractedItem, ExtractionResult, Extractor
from app.pipeline.columns import (
    Word,
    analyze_table,
    assign_to_columns,
    group_rows,
    stitch_multiline,
    strip_leading_enumeration,
)
from app.pipeline.ocr import ocr_page_text, ocr_page_words, postprocess_ocr_text
from app.pipeline.price_parser import parse_amount
from app.pipeline.textquality import assess_text, page_needs_ocr

# Строки-итоги пропускаем (раздел 7.7): не услуги, а суммы.
_TOTAL_MARKERS = ("итого", "всего", "подытог", "сумма по")
# Порог «почти пустой» текстовый слой страницы — гоним на переOCR.
_MIN_TEXT_CHARS = 20


class PdfScanExtractor(Extractor):
    """Скан/битый-OCR PDF. Постранично решает: верить слою или переOCR-ить."""

    name = "pdf_scan"

    def can_handle(self, file_path: str, file_format: str) -> bool:
        # scan_pdf проверяется в реестре раньше pdf (см. registry.py).
        return file_format == "scan_pdf"

    def extract(self, file_path: str) -> ExtractionResult:
        result = ExtractionResult(extractor_used=self.name)
        raw_parts: list[str] = []

        try:
            pdf = pdfplumber.open(file_path)
        except Exception as exc:  # noqa: BLE001 — не валим весь документ из-за одного файла
            result.warn(f"Не удалось открыть PDF: {exc}")
            return result

        with pdf:
            result.page_count = len(pdf.pages)
            for page_index, page in enumerate(pdf.pages):
                page_number = page_index + 1  # 1-based для OCR и source_page
                try:
                    page_text, words, ocr_used = self._page_words(
                        file_path, page, page_number, result
                    )
                except Exception as exc:  # noqa: BLE001
                    result.warn(f"Страница {page_number}: ошибка чтения ({exc})")
                    continue

                if ocr_used:
                    result.ocr_applied = True
                raw_parts.append(page_text)

                page_items = self._items_from_words(words, page_number, result)
                if not page_items:
                    # После (воз)OCR строк всё равно нет — фиксируем, но не падаем.
                    result.warn(
                        f"Страница {page_number}: не распознано ни одной позиции"
                    )
                    continue
                result.items.extend(page_items)

        result.raw_content = "\n".join(raw_parts).strip()
        # Если весь документ пуст — оркестратор пометит error, мы не бросаем.
        return result

    # ------------------------------------------------------------------ #
    # Получение слов страницы: чистый слой -> extract_words, иначе переOCR.
    # ------------------------------------------------------------------ #
    def _page_words(
        self,
        file_path: str,
        page: pdfplumber.page.Page,
        page_number: int,
        result: ExtractionResult,
    ) -> tuple[str, list[Word], bool]:
        """Возвращает (текст страницы для аудита, список Word, был ли OCR)."""
        try:
            layer_text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 — битый слой тоже бывает невытаскиваемым
            layer_text = ""

        nearly_empty = len(layer_text.strip()) < _MIN_TEXT_CHARS
        if nearly_empty or page_needs_ocr(layer_text):
            # Битый встроенный OCR или пустая страница — рендерим и распознаём.
            try:
                words = ocr_page_words(file_path, page_number)
            except Exception as exc:  # noqa: BLE001
                result.warn(f"Страница {page_number}: OCR не выполнен ({exc})")
                # Фолбэк на то, что есть в слое, чтобы не терять страницу целиком.
                return postprocess_ocr_text(layer_text), self._plumber_words(page), False
            try:
                ocr_text = ocr_page_text(file_path, page_number)
            except Exception:  # noqa: BLE001
                ocr_text = " ".join(w.text for w in words)
            quality = assess_text(layer_text)
            result.warn(
                f"Страница {page_number}: переOCR (слой {quality.summary})"
            )
            return ocr_text, words, True

        # Слой чистый — берём слова прямо из pdfplumber.
        return layer_text, self._plumber_words(page), False

    @staticmethod
    def _plumber_words(page: pdfplumber.page.Page) -> list[Word]:
        """Слова чистого текстового слоя -> наш Word с координатами в точках."""
        words: list[Word] = []
        try:
            raw = page.extract_words(use_text_flow=False, keep_blank_chars=False)
        except Exception:  # noqa: BLE001
            return words
        for w in raw:
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

    # ------------------------------------------------------------------ #
    # Геометрия: та же, что у текстового PDF (раздел 7.2 / 7.7).
    # ------------------------------------------------------------------ #
    def _items_from_words(
        self, words: list[Word], page_number: int, result: ExtractionResult
    ) -> list[ExtractedItem]:
        if not words:
            return []

        rows = group_rows(words)
        if not rows:
            return []

        # Границы колонок по плотности строк данных, роли колонок из заголовка
        # или по содержимому (битый OCR часто рушит шапку). Та же логика, что и
        # у текстового PDF — единая точка analyze_table.
        bounds, cmap, header_idx = analyze_table(rows)
        if not bounds:
            return []
        data_rows = rows[header_idx + 1 :] if header_idx >= 0 else rows
        # Склейка многострочных названий (issue #1): та же логика, что у
        # текстового PDF — дозаполняет пустую колонку имени со строк без цены.
        data_rows = stitch_multiline(data_rows, bounds, cmap)

        items: list[ExtractedItem] = []
        category: str | None = None

        for offset, row in enumerate(data_rows):
            cells = assign_to_columns(row, bounds)
            line = row.text().strip()
            if not line:
                continue

            # Итоги/подытоги — не услуги, пропускаем.
            low = line.lower()
            if any(m in low for m in _TOTAL_MARKERS):
                continue

            prices = self._extract_prices(cells, cmap)

            # Строка-секция: текст без цен, занимает ширину -> это категория.
            if not prices:
                if self._looks_like_section(cells, line):
                    category = line
                continue

            name = self._extract_name(cells, cmap, line)
            if not name:
                # Цена есть, а имени нет — повреждённая строка, не теряем молча.
                continue

            code = self._extract_code(cells, cmap)
            source_row = (header_idx + 1 + offset) if header_idx >= 0 else offset

            items.append(
                ExtractedItem(
                    service_name_raw=name,
                    service_code_source=code,
                    prices=prices,
                    category=category,
                    source_page=page_number,
                    source_row=source_row,
                )
            )

        return items

    # ------------------------------------------------------------------ #
    # Разбор ячеек строки.
    # ------------------------------------------------------------------ #
    def _extract_prices(self, cells: list[str], cmap) -> dict[str, object]:
        """Карта подпись_тарифа -> Decimal. Пропускаем ячейки без числа."""
        prices: dict[str, object] = {}
        if cmap is not None and cmap.price_idxs:
            for idx in cmap.price_idxs:
                if idx >= len(cells):
                    continue
                amount = parse_amount(cells[idx])
                if amount is None:
                    continue
                label = cmap.labels.get(idx) or f"Цена {idx}"
                prices[label] = amount
            return prices

        # Без карты заголовка: любую числовую ячейку считаем тарифом,
        # подпись — по позиции (так price_parser потом разложит по порядку).
        price_counter = 0
        for cell in cells:
            amount = parse_amount(cell)
            if amount is None:
                continue
            price_counter += 1
            prices[f"Тариф {price_counter}"] = amount
        return prices

    @staticmethod
    def _extract_name(cells: list[str], cmap, line: str) -> str:
        """Имя услуги: из колонки name по карте, иначе — самая широкая
        нечисловая ячейка строки."""
        if cmap is not None and cmap.name_idx is not None and cmap.name_idx < len(cells):
            candidate = cells[cmap.name_idx].strip()
            if candidate:
                # Колонка «№» слилась с названием — срезаем ведущий номер строки.
                return strip_leading_enumeration(candidate) if cmap.name_has_index else candidate

        # Фолбэк: самая длинная ячейка без распознанной цены.
        best = ""
        for cell in cells:
            cell = cell.strip()
            if not cell or parse_amount(cell) is not None:
                continue
            if len(cell) > len(best):
                best = cell
        # Последний фолбэк — вся строка (битый OCR без чётких колонок).
        return best or line

    @staticmethod
    def _extract_code(cells: list[str], cmap) -> str | None:
        """Код услуги из колонки code, если она размечена."""
        if cmap is not None and cmap.code_idx is not None and cmap.code_idx < len(cells):
            code = cells[cmap.code_idx].strip()
            return code or None
        return None

    @staticmethod
    def _looks_like_section(cells: list[str], line: str) -> bool:
        """Эвристика строки-секции: непустой текст, заполнена одна-две ячейки,
        нет ни одной цены. Типично для заголовков разделов («ГЕМАТОЛОГИЯ»)."""
        if len(line.strip()) < 3:
            return False
        filled = [c for c in cells if c.strip()]
        if not filled:
            return False
        if any(parse_amount(c) is not None for c in filled):
            return False
        # Секция обычно лежит в одной-двух колонках (широкий текст без таблицы).
        return len(filled) <= 2
