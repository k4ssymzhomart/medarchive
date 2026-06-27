"""Тесты нормализации строк (раздел 8.2)."""

from app.normalization.normalize import normalize, normalize_name, tokens


def test_normalize_lowercase_spaces():
    assert normalize("  Общий   Анализ  Крови ") == "общий анализ крови"


def test_normalize_abbreviation_oak():
    assert normalize("ОАК") == "общий анализ крови"


def test_normalize_yo():
    assert normalize("приём") == normalize("прием")


def test_normalize_dmn():
    out = normalize("Консультация врача д.м.н.")
    assert "доктор медицинских наук" in out


def test_normalize_name_strips_legal_forms():
    a = normalize_name("ТОО Клиника Здоровье")
    assert "тоо" not in a
    assert "здоровье" in a


def test_tokens():
    assert tokens("Общий анализ крови") == {"общий", "анализ", "крови"}
