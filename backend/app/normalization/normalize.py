"""Нормализация строк для сопоставления (раздел 8.2, уровень 1).

Нижний регистр, схлопывание пробелов, унификация сокращений
(«д.м.н.», «к.м.н.», «ОАК»). Используется и для точного матча,
и как ключ лексического индекса.
"""

from __future__ import annotations

import re

# Унификация частых медицинских сокращений и аббревиатур.
ABBREVIATIONS = {
    "оак": "общий анализ крови",
    "оам": "общий анализ мочи",
    "бак": "биохимический анализ крови",
    "экг": "электрокардиография",
    "ээг": "электроэнцефалография",
    "узи": "ультразвуковое исследование",
    "кт": "компьютерная томография",
    "мрт": "магнитно резонансная томография",
    "д.м.н.": "доктор медицинских наук",
    "дмн": "доктор медицинских наук",
    "к.м.н.": "кандидат медицинских наук",
    "кмн": "кандидат медицинских наук",
    "врач высшей категории": "врач высшей категории",
}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize(text: str, expand_abbr: bool = True) -> str:
    """Каноническая форма строки для матчинга."""
    if not text:
        return ""
    s = text.lower().strip()
    s = s.replace("ё", "е")

    if expand_abbr:
        # Сначала точечные аббревиатуры (до удаления пунктуации).
        for abbr, full in ABBREVIATIONS.items():
            if "." in abbr:
                s = s.replace(abbr, f" {full} ")

    s = _PUNCT_RE.sub(" ", s)
    s = _SPACE_RE.sub(" ", s).strip()

    if expand_abbr:
        tokens = s.split()
        tokens = [ABBREVIATIONS.get(t, t) for t in tokens]
        s = " ".join(tokens)
        s = _SPACE_RE.sub(" ", s).strip()

    return s


def normalize_name(text: str) -> str:
    """Нормализация имени партнёра/клиники для дедупликации (раздел 6.1)."""
    if not text:
        return ""
    s = text.lower().strip().replace("ё", "е")
    s = re.sub(r'["«»\'`]', " ", s)
    s = re.sub(r"\b(тоо|ип|ао|оао|зао|клиника|медицинский центр|мц|гкп)\b", " ", s)
    s = _PUNCT_RE.sub(" ", s)
    return _SPACE_RE.sub(" ", s).strip()


def tokens(text: str) -> set[str]:
    return set(normalize(text).split())
