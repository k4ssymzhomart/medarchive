"""Шаг 0. Router типов файла (раздел 7.1).

Определяет формат по расширению и сигнатуре, классифицирует PDF на
текстовый и скан/битый, парсит дату прайса из имени файла.
"""

from __future__ import annotations

import os
import re
from datetime import date

from app.models import FileFormat

_MAGIC = {
    b"%PDF": "pdf",
    b"PK\x03\x04": "zipxml",  # docx/xlsx — это zip
    b"\xd0\xcf\x11\xe0": "ole",  # старый .xls/.doc (OLE2)
}

YEAR_RE = re.compile(r"(20\d{2})")
FULL_DATE_RE = re.compile(r"(\d{1,2})[.\-_](\d{1,2})[.\-_](20\d{2})")


def sniff_magic(file_path: str) -> str | None:
    try:
        with open(file_path, "rb") as fh:
            head = fh.read(8)
    except OSError:
        return None
    for sig, kind in _MAGIC.items():
        if head.startswith(sig):
            return kind
    return None


def detect_format(file_path: str) -> FileFormat:
    """Формат по расширению, подтверждённый сигнатурой. PDF later классифицируется
    на pdf/scan_pdf в is_scanned_pdf (требует чтения страниц)."""
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    magic = sniff_magic(file_path)

    if ext == "pdf" or magic == "pdf":
        return FileFormat.pdf
    if ext == "docx":
        return FileFormat.docx
    if ext == "xlsx":
        return FileFormat.xlsx
    if ext == "xls":
        return FileFormat.xls
    # Фолбэк по сигнатуре, если расширение нестандартное.
    if magic == "zipxml":
        return FileFormat.xlsx
    if magic == "ole":
        return FileFormat.xls
    raise ValueError(f"Не удалось определить формат файла: {file_path}")


def parse_effective_date(file_name: str, raw_text: str | None = None) -> date | None:
    """Дата прайса из имени файла (год есть почти всегда), подтверждается
    из содержимого. Возвращает 1 января найденного года, если день/месяц нет."""
    name = os.path.basename(file_name)

    m = FULL_DATE_RE.search(name)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        try:
            return date(y, mo, d)
        except ValueError:
            pass

    m = YEAR_RE.search(name)
    if m:
        return date(int(m.group(1)), 1, 1)

    if raw_text:
        m = YEAR_RE.search(raw_text[:2000])
        if m:
            return date(int(m.group(1)), 1, 1)
    return None


def classify_pdf(file_path: str, sample_pages: int = 3) -> FileFormat:
    """Классифицирует PDF: текстовый (FileFormat.pdf) или скан/битый
    (FileFormat.scan_pdf). Решает по доле валидной кириллицы первых страниц.
    """
    import pdfplumber

    from app.pipeline.textquality import assess_text

    texts: list[str] = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:sample_pages]:
                texts.append(page.extract_text() or "")
    except Exception:
        return FileFormat.scan_pdf

    combined = "\n".join(texts)
    quality = assess_text(combined)
    return FileFormat.scan_pdf if quality.is_corrupt else FileFormat.pdf
