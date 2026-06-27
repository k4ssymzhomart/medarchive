"""Тесты склейки многострочных названий услуг в PDF (issue #1).

Проверяют две беды реальных прайсов на синтетических словах (без OCR/pdfplumber,
поэтому стабильны в CI):
- Клиника 3: название лежит на строках НИЖЕ ценовой строки, а в колонке имени
  ценовой строки пусто -> в имя попадает биоматериал «кровь с ЭДТА».
- Клиника 4: колонка «№» слита с названием («9 Выездная консультация врача»),
  из-за ведущего номера колонка названий ошибочно уезжает в цены, а имя в код.
"""

from app.pipeline.columns import (
    ColumnMap,
    Row,
    Word,
    _is_index_sequence,
    _looks_like_price,
    analyze_table,
    assign_to_columns,
    infer_column_map,
    stitch_multiline,
    strip_leading_enumeration,
)


def _w(text: str, x0: float, top: float) -> Word:
    """Слово с шириной пропорционально длине текста (как в test_columns)."""
    return Word(text=text, x0=x0, x1=x0 + 6 * len(text), top=top, bottom=top + 10)


def _row(*words: Word) -> Row:
    return Row(words=list(words), top=min(w.top for w in words))


# --- мелкие предикаты -------------------------------------------------------


def test_is_index_sequence_with_section_resets():
    # Сквозной номер строки со сбросами на 1 в начале раздела.
    assert _is_index_sequence([9, 10, 1, 2, 3, 1, 2]) is True
    assert _is_index_sequence([1, 2, 3, 4, 5]) is True
    # Цены так не выглядят.
    assert _is_index_sequence([880, 1410, 3980, 2985]) is False


def test_looks_like_price_handles_currency_and_leading_number():
    assert _looks_like_price("5000 тенге") is True
    assert _looks_like_price("9000 тг") is True
    assert _looks_like_price("148 500") is True
    # Название с ведущим номером строки — это НЕ цена.
    assert _looks_like_price("9 Выездная консультация врача") is False
    assert _looks_like_price("Общий анализ крови") is False


def test_strip_leading_enumeration():
    assert strip_leading_enumeration("9 Выездная консультация врача") == "Выездная консультация врача"
    assert strip_leading_enumeration("10. Анализ крови") == "Анализ крови"
    # Настоящие названия с цифрой не калечим.
    assert strip_leading_enumeration("3D реконструкция") == "3D реконструкция"
    assert strip_leading_enumeration("16600") == "16600"


def test_assign_to_columns_preserves_top_then_left_order():
    # После склейки слова разных уровней Y должны читаться сверху вниз,
    # а не перемешиваться по X внутри колонки.
    bounds = [0.0]
    row = Row(
        words=[
            _w("формулой", 100, 60),  # вторая строка
            _w("Клинический", 100, 40),  # первая строка, тот же X
            _w("анализ", 200, 40),
        ],
        top=40,
    )
    assert assign_to_columns(row, bounds)[0] == "Клинический анализ формулой"


# --- Клиника 4: колонка «№» слита с названием -------------------------------


def test_number_plus_name_column_is_name_not_price():
    # Колонка, где ячейки «N <название>», должна стать именем, не ценой.
    bounds = [40.0, 300.0]
    rows = [
        _row(_w("9 Выездная консультация врача", 45, 10), _w("148500", 305, 10)),
        _row(_w("10 Снятие швов", 45, 30), _w("18700", 305, 30)),
        _row(_w("1 Перевязка раны", 45, 50), _w("5000", 305, 50)),
    ]
    cmap = infer_column_map(rows, bounds)
    assert cmap.name_idx == 0
    assert 0 not in cmap.price_idxs
    assert cmap.price_idxs == [1]


def test_analyze_table_drops_row_number_as_code():
    # Геометрия Клиники 4: «№» отдельной колонкой в заголовке, но в данных номер
    # строки слит с названием (нет зазора). Колонка «Единица» отделяет цену.
    # Заголовок: «№» (код) + «Единица» + «Цена» -> find_header по якорям.
    header = _row(_w("№", 45, 0), _w("Единица", 250, 0), _w("Цена", 330, 0))
    data = [
        _row(_w("9 Выездная консультация врача", 45, 20), _w("пакет", 250, 20), _w("148500", 330, 20)),
        _row(_w("10 Снятие швов", 45, 40), _w("час", 250, 40), _w("18700", 330, 40)),
        _row(_w("1 Перевязка раны", 45, 60), _w("раз", 250, 60), _w("5000", 330, 60)),
    ]
    bounds, cmap, header_idx = analyze_table([header, *data])
    assert header_idx == 0
    assert cmap.name_idx is not None
    # Сквозной номер строки не должен остаться кодом услуги.
    assert cmap.name_has_index is True
    assert cmap.code_idx is None
    name_cell = assign_to_columns(data[0], bounds)[cmap.name_idx]
    assert strip_leading_enumeration(name_cell) == "Выездная консультация врача"


# --- Клиника 3: название на строках ниже ценовой ----------------------------


def _k3_bounds_cmap():
    # Колонки: 1 имя, 2 код, 3 биоматериал, 4 цена.
    bounds = [80.0, 110.0, 315.0, 385.0, 465.0]
    cmap = ColumnMap(name_idx=1, code_idx=2, price_idxs=[4])
    return bounds, cmap


def test_stitch_fills_empty_name_from_following_rows():
    bounds, cmap = _k3_bounds_cmap()
    # Ценовая строка: имя пусто, есть биоматериал и цена.
    anchor = _row(_w("кровь с ЭДТА", 390, 43), _w("880", 470, 43))
    code_row = _row(_w("В02.110.002", 320, 47))
    name_row = _row(_w("Общий анализ крови (ОАК без СОЭ)", 115, 50))
    # Следующая ценовая строка — граница склейки.
    next_anchor = _row(_w("кровь с ЭДТА", 390, 55), _w("3980", 470, 55))

    stitched = stitch_multiline([anchor, code_row, name_row, next_anchor], bounds, cmap)
    # Три строки до next_anchor схлопнулись в одну, плюс next_anchor.
    assert len(stitched) == 2
    cells = assign_to_columns(stitched[0], bounds)
    assert cells[cmap.name_idx] == "Общий анализ крови (ОАК без СОЭ)"
    assert cells[cmap.code_idx] == "В02.110.002"
    assert cells[4] == "880"


def test_stitch_assembles_multiline_name_in_order():
    bounds, cmap = _k3_bounds_cmap()
    anchor = _row(_w("кровь с ЭДТА", 390, 54), _w("3980", 470, 54))
    line1 = _row(_w("Клинический анализ крови с лейкоцитарной", 115, 59))
    line2 = _row(_w("формулой и измерением скорости оседания", 115, 72))
    line3 = _row(_w("эритроцитов", 115, 84))
    next_anchor = _row(_w("кровь с ЭДТА", 390, 90), _w("2360", 470, 90))

    stitched = stitch_multiline([anchor, line1, line2, line3, next_anchor], bounds, cmap)
    name = assign_to_columns(stitched[0], bounds)[cmap.name_idx]
    assert name == (
        "Клинический анализ крови с лейкоцитарной "
        "формулой и измерением скорости оседания эритроцитов"
    )


def test_stitch_stops_at_uppercase_section_heading():
    bounds, cmap = _k3_bounds_cmap()
    anchor = _row(_w("кровь с ЭДТА", 390, 136), _w("1340", 470, 136))
    name_row = _row(_w("Подсчет ретикулоцитов", 115, 143))
    section = _row(_w("ИММУНОГЕМАТОЛОГИЧЕСКИЕ ИССЛЕДОВАНИЯ", 115, 151))
    next_anchor = _row(_w("кровь с ЭДТА", 390, 161), _w("2320", 470, 161))

    stitched = stitch_multiline([anchor, name_row, section, next_anchor], bounds, cmap)
    # anchor + name_row склеились; секция и next_anchor остались отдельными.
    assert len(stitched) == 3
    assert assign_to_columns(stitched[0], bounds)[cmap.name_idx] == "Подсчет ретикулоцитов"
    assert "ИММУНОГЕМАТОЛОГИЧЕСКИЕ" in assign_to_columns(stitched[1], bounds)[cmap.name_idx]


def test_stitch_is_noop_when_name_present():
    # Штатные прайсы: у ценовой строки имя уже есть -> склейки нет, регрессий нет.
    bounds, cmap = _k3_bounds_cmap()
    r1 = _row(_w("Консультация терапевта", 115, 40), _w("9000", 470, 40))
    r2 = _row(_w("Консультация хирурга", 115, 52), _w("12000", 470, 52))
    stitched = stitch_multiline([r1, r2], bounds, cmap)
    assert len(stitched) == 2
    assert assign_to_columns(stitched[0], bounds)[cmap.name_idx] == "Консультация терапевта"
