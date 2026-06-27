"""Детектор качества текстового слоя (раздел 7.1, 7.3).

Наш козырь по критерию 30 процентов: отличить чистый текстовый слой PDF
от битого встроенного OCR («Прейскурант иен», «yc.iv!», «Yliliepiia.i»).
Критерий — доля валидных кириллических слов и латинских вкраплений
внутри предположительно русских слов.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CYRILLIC_RE = re.compile(r"[а-яёА-ЯЁ]")
LATIN_RE = re.compile(r"[a-zA-Z]")
WORD_RE = re.compile(r"[А-Яа-яЁёA-Za-z]{2,}")

# Якоря: если текст содержит осмысленные русские слова прайса — он валиден.
ANCHOR_WORDS = (
    "наименование", "услуга", "услуги", "цена", "стоимость", "код",
    "прайс", "прейскурант", "консультация", "анализ", "приём", "прием",
    "исследование", "тенге", "тг", "категория", "раздел",
)


@dataclass
class TextQuality:
    char_count: int
    cyrillic_ratio: float       # доля кириллицы среди букв
    contamination: float        # доля «грязных» слов (латиница внутри кириллицы)
    anchor_hits: int            # сколько якорных слов найдено
    is_corrupt: bool            # вердикт: нужен переOCR

    @property
    def summary(self) -> str:
        return (
            f"chars={self.char_count} cyr={self.cyrillic_ratio:.2f} "
            f"contam={self.contamination:.2f} anchors={self.anchor_hits} "
            f"corrupt={self.is_corrupt}"
        )


def _is_dirty_word(word: str) -> bool:
    """Слово грязное, если в нём смешаны кириллица и латиница, либо много
    небуквенного мусора (типичный артефакт битого OCR: «Yliliepiia.i»)."""
    has_cyr = bool(CYRILLIC_RE.search(word))
    has_lat = bool(LATIN_RE.search(word))
    if has_cyr and has_lat:
        return True
    # одинокие латинские «слова» среди русского текста тоже подозрительны
    return False


def assess_text(text: str) -> TextQuality:
    """Оценить качество извлечённого текстового слоя."""
    text = text or ""
    letters = CYRILLIC_RE.findall(text) + LATIN_RE.findall(text)
    cyr = CYRILLIC_RE.findall(text)
    cyrillic_ratio = (len(cyr) / len(letters)) if letters else 0.0

    words = WORD_RE.findall(text)
    cyr_words = [w for w in words if CYRILLIC_RE.search(w)]
    dirty = [w for w in words if _is_dirty_word(w)]
    contamination = (len(dirty) / len(cyr_words)) if cyr_words else 0.0

    low = text.lower()
    anchor_hits = sum(1 for a in ANCHOR_WORDS if a in low)

    # Вердикт: мало текста, либо мало кириллицы, либо высокая загрязнённость,
    # при этом якорей почти нет.
    is_corrupt = False
    if len(text.strip()) < 40:
        is_corrupt = True
    elif cyrillic_ratio < 0.45 and anchor_hits < 2:
        is_corrupt = True
    elif contamination > 0.18 and anchor_hits < 3:
        is_corrupt = True

    return TextQuality(
        char_count=len(text),
        cyrillic_ratio=cyrillic_ratio,
        contamination=contamination,
        anchor_hits=anchor_hits,
        is_corrupt=is_corrupt,
    )


def page_needs_ocr(page_text: str) -> bool:
    """Нужно ли переOCR ивать конкретную страницу."""
    return assess_text(page_text).is_corrupt
