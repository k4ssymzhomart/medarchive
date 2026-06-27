"""Переoor битых страниц (раздел 7.3).

Рендерим страницу PDF в изображение высокого разрешения и прогоняем Tesseract
с русским языком, режим сегментации под таблицы. Tesseract отдаёт bounding box
каждого слова — это даёт нам те же координаты, что pdfplumber, поэтому дальше
работает общая геометрия колонок (columns.py).
"""

from __future__ import annotations

import re

from app.config import settings
from app.pipeline.columns import Word

# Типичные подмены битого OCR -> чиним постобработкой (раздел 7.3).
OCR_FIXES = {
    "иен": "цен",
    "Иен": "Цен",
    "Прейскурант иен": "Прейскурант цен",
}
_MULTISPACE = re.compile(r"[ \t]+")


def postprocess_ocr_text(text: str) -> str:
    """Чистим артефакты, чиним типичные подмены, нормализуем пробелы."""
    if not text:
        return ""
    for bad, good in OCR_FIXES.items():
        text = text.replace(bad, good)
    text = _MULTISPACE.sub(" ", text)
    return text.strip()


def render_page_to_image(file_path: str, page_number: int, dpi: int | None = None):
    """Рендер одной страницы (1-based) в PIL.Image."""
    from pdf2image import convert_from_path

    dpi = dpi or settings.ocr_dpi
    images = convert_from_path(file_path, dpi=dpi, first_page=page_number, last_page=page_number)
    return images[0]


def ocr_page_words(file_path: str, page_number: int, languages: str | None = None) -> list[Word]:
    """OCR страницы -> список Word с координатами bounding box.

    Координаты приводятся к масштабу pdfplumber (точки PDF при 72 dpi),
    чтобы columns.py работал одинаково для текстового и сканированного PDF.
    """
    import pytesseract
    from pytesseract import Output

    languages = languages or settings.ocr_languages
    dpi = settings.ocr_dpi
    image = render_page_to_image(file_path, page_number, dpi=dpi)

    # psm 6: единый блок текста (таблица без линий).
    data = pytesseract.image_to_data(
        image, lang=languages, config="--psm 6", output_type=Output.DICT
    )

    scale = 72.0 / dpi  # пиксели OCR -> точки PDF
    words: list[Word] = []
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        conf = float(data.get("conf", ["-1"])[i] or -1)
        if conf >= 0 and conf < 30:  # отбрасываем совсем мусорные распознавания
            continue
        x = float(data["left"][i]) * scale
        y = float(data["top"][i]) * scale
        w = float(data["width"][i]) * scale
        h = float(data["height"][i]) * scale
        words.append(Word(text=postprocess_ocr_text(text), x0=x, x1=x + w, top=y, bottom=y + h))
    return words


def ocr_page_text(file_path: str, page_number: int, languages: str | None = None) -> str:
    """OCR страницы -> плоский текст (для raw_content и детекции)."""
    import pytesseract

    languages = languages or settings.ocr_languages
    image = render_page_to_image(file_path, page_number)
    text = pytesseract.image_to_string(image, lang=languages, config="--psm 6")
    return postprocess_ocr_text(text)
