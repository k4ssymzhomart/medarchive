"""Тесты нормализации строк (раздел 8.2)."""

from app.normalization.normalize import normalize, normalize_code, normalize_name, tokens


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


# --- normalize_code: коды тарификатора и кириллические гомоглифы (Задача B.2) ---
def test_normalize_code_basic():
    assert normalize_code("A02.004.000") == "A02.004.000"
    assert normalize_code("  a02.004.000  ") == "A02.004.000"
    assert normalize_code("A02 004 000") == "A02004000"  # пробелы убираются


def test_normalize_code_homoglyphs():
    # Кириллические В, О, С, А -> латинские B, O, C, A
    assert normalize_code("В02.110.002") == "B02.110.002"
    assert normalize_code("С03.328") == "C03.328"
    assert normalize_code("А02.004.000") == "A02.004.000"
    # кириллический и латинский код одной услуги приводятся к одной форме
    assert normalize_code("В06.670.012") == normalize_code("B06.670.012")


def test_normalize_code_empty():
    assert normalize_code(None) is None
    assert normalize_code("") is None
    assert normalize_code("   ") is None
