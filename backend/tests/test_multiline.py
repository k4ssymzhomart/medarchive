"""Тесты склейки многострочных названий услуг в PDF (issue #1).

Проверяют обе беды реальных прайсов на синтетических словах (без OCR/pdfplumber,
поэтому стабильны в CI):
- Клиника 3: название лежит на строках НИЖЕ ценовой строки, а в колонке имени
  ценовой строки пусто -> в имя попадает биоматериал «кровь с ЭДТА».
- Клиника 4: колонка «№» слита с названием («9 Выездная консультация врача»), а
  иногда название обёрнуто вокруг ценовой строки с одним номером «6».
"""

from app.pipeline.columns import (
    ColumnMap,
    Row,
    Word,
    _is_absorb_boundary,
    _is_bare_index,
    _is_document_preamble,
    _is_index_sequence,
    _is_section_heading,
    _line_gap_limit,
    _looks_like_price,
    _name_column_has_indices,
    _name_incomplete,
    analyze_table,
    assign_to_columns,
    infer_column_map,
    stitch_multiline,
    strip_leading_enumeration,
)
from app.pipeline.extractors.pdf_text import PdfTextExtractor


def _w(text: str, x0: float, top: float) -> Word:
    """Слово с шириной пропорционально длине текста (как в test_columns)."""
    return Word(text=text, x0=x0, x1=x0 + 6 * len(text), top=top, bottom=top + 10)


def _row(*words: Word) -> Row:
    return Row(words=list(words), top=min(w.top for w in words))


# --- мелкие предикаты -------------------------------------------------------


def test_is_index_sequence_with_section_resets():
    assert _is_index_sequence([9, 10, 1, 2, 3, 1, 2]) is True
    assert _is_index_sequence([1, 2, 3, 4, 5]) is True
    # Цены так не выглядят.
    assert _is_index_sequence([880, 1410, 3980, 2985]) is False
    # Постоянная колонка (одинаковые цены) — НЕ нумерация (нет прогресса).
    assert _is_index_sequence([5000, 5000, 5000, 5000]) is False


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


def test_is_bare_index():
    assert _is_bare_index("6") is True
    assert _is_bare_index("10.") is True
    assert _is_bare_index("3)") is True
    assert _is_bare_index("6 Анализ") is False
    assert _is_bare_index("16600") is False


def test_name_incomplete():
    # Незакрытая скобка / знак переноса — название продолжается ниже.
    assert _name_incomplete("Определение натрия (Na) в (анализаторе") is True
    assert _name_incomplete("Антитела к антигенам,") is True
    assert _name_incomplete("Консультация терапевта") is False
    assert _name_incomplete("Анализ крови (расширенный)") is False


def test_is_section_heading():
    # Короткий однословный капс — заголовок (Клиника 3: ЦИТОЛОГИЯ, ГОРМОНЫ).
    assert _is_section_heading(["ЦИТОЛОГИЯ"]) is True
    assert _is_section_heading(["ГОРМОНЫ"]) is True
    assert _is_section_heading(["ИММУНОГЕМАТОЛОГИЧЕСКИЕ", "ИССЛЕДОВАНИЯ"]) is True
    # Капсовое ПРОДОЛЖЕНИЕ названия (список антител) с цифрами — НЕ заголовок.
    assert _is_section_heading(["PML, gp21,0, LK.M-1, LC-1, SLA/LP, Ro-52),"]) is False
    # Сноска в скобках и строчное продолжение — не заголовок.
    assert _is_section_heading(["(ОАК + СРБ. без СОЭ)"]) is False
    assert _is_section_heading(["Подсчет ретикулоцитов"]) is False


# --- Клиника 4: колонка «№» слита с названием -------------------------------


def test_number_plus_name_column_is_name_not_price():
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
    header = _row(_w("№", 45, 0), _w("Единица", 250, 0), _w("Цена", 330, 0))
    data = [
        _row(_w("9 Выездная консультация врача", 45, 20), _w("пакет", 250, 20), _w("148500", 330, 20)),
        _row(_w("10 Снятие швов", 45, 40), _w("час", 250, 40), _w("18700", 330, 40)),
        _row(_w("1 Перевязка раны", 45, 60), _w("раз", 250, 60), _w("5000", 330, 60)),
    ]
    bounds, cmap, header_idx = analyze_table([header, *data])
    assert header_idx == 0
    assert cmap.name_idx is not None
    assert cmap.name_has_index is True
    assert cmap.code_idx is None
    name_cell = assign_to_columns(data[0], bounds)[cmap.name_idx]
    assert strip_leading_enumeration(name_cell) == "Выездная консультация врача"


# --- assign_to_columns: обычная строка по X, склеенная по готовым ячейкам ----


def test_assign_to_columns_normal_row_uses_x_order():
    bounds = [0.0, 100.0]
    row = _row(_w("Бета", 110, 40), _w("Альфа", 10, 40))
    assert assign_to_columns(row, bounds) == ["Альфа", "Бета"]


def test_assign_to_columns_uses_precomputed_cells():
    row = Row(words=[], top=0.0, cells=["имя", "код", "100"])
    assert assign_to_columns(row, [0.0, 1.0, 2.0]) == ["имя", "код", "100"]


# --- Клиника 3: название на строках ниже ценовой ----------------------------


def _k3_bounds_cmap(name_has_index: bool = False):
    # Колонки: 1 имя, 2 код, 3 биоматериал, 4 цена.
    bounds = [80.0, 110.0, 315.0, 385.0, 465.0]
    cmap = ColumnMap(name_idx=1, code_idx=2, price_idxs=[4], name_has_index=name_has_index)
    return bounds, cmap


def test_stitch_fills_empty_name_from_following_rows():
    bounds, cmap = _k3_bounds_cmap()
    anchor = _row(_w("кровь с ЭДТА", 390, 43), _w("880", 470, 43))
    code_row = _row(_w("В02.110.002", 320, 47))
    name_row = _row(_w("Общий анализ крови (ОАК без СОЭ)", 115, 50))
    next_anchor = _row(_w("кровь с ЭДТА", 390, 55), _w("3980", 470, 55))

    stitched = stitch_multiline([anchor, code_row, name_row, next_anchor], bounds, cmap)
    assert len(stitched) == 2
    cells = assign_to_columns(stitched[0], bounds)
    assert cells[cmap.name_idx] == "Общий анализ крови (ОАК без СОЭ)"
    assert cells[cmap.code_idx] == "В02.110.002"
    assert cells[4] == "880"
    # Биоматериал остаётся в своей колонке, в имя не течёт.
    assert cells[3] == "кровь с ЭДТА"


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


def test_stitch_leaves_partial_name_anchor_untouched():
    # Консервативно: ценовую строку с уже заполненным (пусть и оборванным) именем
    # не трогаем — это исключает над-поглощение чужих услуг и преамбулы.
    bounds, cmap = _k3_bounds_cmap()
    anchor = _row(_w("Na (натрий) (Определение натрия (Na) в", 115, 40), _w("700", 470, 40))
    cont = _row(_w("сыворотке крови на анализаторе)", 115, 52))
    next_anchor = _row(_w("Общий белок", 115, 64), _w("900", 470, 64))
    stitched = stitch_multiline([anchor, cont, next_anchor], bounds, cmap)
    assert len(stitched) == 3
    assert assign_to_columns(stitched[0], bounds)[cmap.name_idx] == (
        "Na (натрий) (Определение натрия (Na) в"
    )


def test_stitch_stops_at_big_vertical_gap():
    # Чужая строка выше отделена крупным вертикальным зазором -> вверх не тянем.
    bounds, cmap = _k3_bounds_cmap()
    far = _row(_w("Цитологическое исследование мазка", 115, 10))  # большой зазор ниже
    name_above = _row(_w("Гистологическое исследование", 115, 60))
    anchor = _row(_w("В08.1", 320, 66), _w("9330", 470, 66))  # имя пустое
    below = _row(_w("биопсийного материала", 115, 72))
    stitched = stitch_multiline([far, name_above, anchor, below], bounds, cmap)
    merged = [assign_to_columns(r, bounds)[cmap.name_idx] for r in stitched if r.cells]
    assert merged == ["Гистологическое исследование биопсийного материала"]
    # Дальняя строка за зазором осталась отдельной, в имя не попала.
    assert any(assign_to_columns(r, bounds)[cmap.name_idx] == "Цитологическое исследование мазка"
               for r in stitched if r.cells is None)


def test_stitch_stops_at_contract_preamble():
    # Боилерплейт договора над пустым anchor не должен попасть в название.
    bounds, cmap = _k3_bounds_cmap()
    pre1 = _row(_w("Приложение № 1 от 01.01.2026", 115, 40))
    pre2 = _row(_w("к договору на оказание услуг", 115, 47))
    name_above = _row(_w("Гистологическое исследование", 115, 54))
    anchor = _row(_w("В08.1", 320, 60), _w("9330", 470, 60))
    stitched = stitch_multiline([pre1, pre2, name_above, anchor], bounds, cmap)
    merged = [assign_to_columns(r, bounds)[cmap.name_idx] for r in stitched if r.cells]
    assert merged == ["Гистологическое исследование"]
    assert _is_absorb_boundary(["Приложение № 1 от 01.01.2026"]) is True
    assert _is_absorb_boundary(["к договору на оказание услуг"]) is True


def test_stitch_stops_at_second_code_distinct_services():
    # Две услуги, у каждой свой код, не должны слиться в одно имя.
    bounds, cmap = _k3_bounds_cmap()
    anchor = _row(_w("кровь с ЭДТА", 390, 40), _w("880", 470, 40))
    s1 = _row(_w("Т4 свободный", 115, 47), _w("В06.203", 320, 47))
    s2 = _row(_w("Анти-ТГ антитела", 115, 54), _w("В06.202", 320, 54))
    nxt = _row(_w("кровь с ЭДТА", 390, 61), _w("1500", 470, 61))
    stitched = stitch_multiline([anchor, s1, s2, nxt], bounds, cmap)
    merged = assign_to_columns(stitched[0], bounds)
    assert merged[cmap.name_idx] == "Т4 свободный"
    assert merged[cmap.code_idx] == "В06.203"
    # Вторая услуга осталась отдельной строкой, в имя первой не влилась.
    names = [assign_to_columns(r, bounds)[cmap.name_idx] for r in stitched]
    assert "Анти-ТГ антитела" in names


def test_name_column_has_indices_content_based():
    # Колонка названия с ведущими номерами распознаётся по содержимому (битый «№»).
    bounds = [40.0, 300.0]
    rows = [
        _row(_w("9 Выездная консультация врача", 45, 10), _w("148500", 305, 10)),
        _row(_w("10 Снятие швов", 45, 30), _w("18700", 305, 30)),
        _row(_w("11 Перевязка раны", 45, 50), _w("5000", 305, 50)),
        _row(_w("12 Гипсовая повязка", 45, 70), _w("7000", 305, 70)),
        _row(_w("13 Снятие гипса", 45, 90), _w("3000", 305, 90)),
    ]
    assert _name_column_has_indices(rows, bounds, 0) is True
    # Обычная колонка названий — без ведущих номеров.
    plain = [_row(_w("Консультация терапевта", 45, 10), _w("9000", 305, 10)) for _ in range(5)]
    assert _name_column_has_indices(plain, bounds, 0) is False


def test_stitch_bare_number_anchor_absorbs_above_and_below():
    # C2 (Клиника 4): название обёрнуто вокруг ценовой строки с одним номером.
    bounds = [40.0, 250.0, 330.0]
    cmap = ColumnMap(name_idx=0, price_idxs=[2], name_has_index=True)
    line1 = _row(_w("Удаление ногтевой пластины (вследствие травмы, вросшего", 45, 392))
    anchor = _row(_w("6", 45, 397), _w("операция", 250, 397), _w("17600", 330, 397))
    line2 = _row(_w("ногтя, грибкового поражения)", 45, 404))
    next_anchor = _row(_w("Перевязка", 45, 420), _w("раз", 250, 420), _w("3000", 330, 420))
    stitched = stitch_multiline([line1, anchor, line2, next_anchor], bounds, cmap)
    names = [assign_to_columns(r, bounds)[0] for r in stitched]
    assert "Удаление ногтевой пластины (вследствие травмы, вросшего ногтя, грибкового поражения)" in names
    # Голый номер «6» не остался названием.
    assert "6" not in names


def test_stitch_stops_at_uppercase_section_heading():
    bounds, cmap = _k3_bounds_cmap()
    anchor = _row(_w("кровь с ЭДТА", 390, 136), _w("1340", 470, 136))
    name_row = _row(_w("Подсчет ретикулоцитов", 115, 143))
    section = _row(_w("ИММУНОГЕМАТОЛОГИЧЕСКИЕ ИССЛЕДОВАНИЯ", 115, 151))
    next_anchor = _row(_w("кровь с ЭДТА", 390, 161), _w("2320", 470, 161))
    stitched = stitch_multiline([anchor, name_row, section, next_anchor], bounds, cmap)
    assert len(stitched) == 3
    assert assign_to_columns(stitched[0], bounds)[cmap.name_idx] == "Подсчет ретикулоцитов"
    assert "ИММУНОГЕМАТОЛОГИЧЕСКИЕ" in assign_to_columns(stitched[1], bounds)[cmap.name_idx]


def test_stitch_stops_at_short_section_heading():
    # EH-1: короткий капсовый заголовок (ЦИТОЛОГИЯ) тоже граница, не часть имени.
    bounds, cmap = _k3_bounds_cmap()
    anchor = _row(_w("кровь с ЭДТА", 390, 40), _w("880", 470, 40))
    name_row = _row(_w("Реакция Вассермана", 115, 47))
    section = _row(_w("ЦИТОЛОГИЯ", 115, 55))
    next_anchor = _row(_w("кровь с ЭДТА", 390, 63), _w("1500", 470, 63))
    stitched = stitch_multiline([anchor, name_row, section, next_anchor], bounds, cmap)
    assert assign_to_columns(stitched[0], bounds)[cmap.name_idx] == "Реакция Вассермана"
    assert any(
        assign_to_columns(r, bounds)[cmap.name_idx] == "ЦИТОЛОГИЯ" for r in stitched
    )


def test_stitch_absorbs_allcaps_continuation_with_digits():
    # EH-2: капсовое продолжение названия с цифрами (список антител) НЕ заголовок,
    # должно склеиться, а не разорвать услугу на три.
    bounds, cmap = _k3_bounds_cmap()
    anchor = _row(_w("кровь с ЭДТА", 390, 376), _w("34000", 470, 376))
    line1 = _row(_w("Антитела к антигенам печени (АМА-М2, М2-ЗЕ,", 115, 381))
    line2 = _row(_w("PML, gp21,0, LK.M-1, LC-1, SLA/LP, Ro-52),", 115, 392))
    line3 = _row(_w("иммуноблот", 115, 404))
    next_anchor = _row(_w("кровь с ЭДТА", 390, 416), _w("2000", 470, 416))
    stitched = stitch_multiline([anchor, line1, line2, line3, next_anchor], bounds, cmap)
    name = assign_to_columns(stitched[0], bounds)[cmap.name_idx]
    assert "PML, gp21,0, LK.M-1, LC-1, SLA/LP, Ro-52)," in name
    assert name.endswith("иммуноблот")


def test_stitch_empty_anchor_stops_at_next_service_when_name_complete():
    # Пустой anchor добирает имя, и как только оно ЦЕЛОЕ, заглавная строка следующей
    # услуги уже не тянется (проверяем именно разрыв по завершённости имени).
    bounds, cmap = _k3_bounds_cmap()
    anchor = _row(_w("кровь с ЭДТА", 390, 40), _w("100000", 470, 40))
    name1 = _row(_w("Удаление атеромы (полное)", 115, 47))
    next_name = _row(_w("Краевая резекция ногтевой пластины", 115, 54))
    next_anchor = _row(_w("кровь с ЭДТА", 390, 61), _w("25000", 470, 61))
    stitched = stitch_multiline([anchor, name1, next_name, next_anchor], bounds, cmap)
    assert assign_to_columns(stitched[0], bounds)[cmap.name_idx] == "Удаление атеромы (полное)"
    names = [assign_to_columns(r, bounds)[cmap.name_idx] for r in stitched]
    assert "Краевая резекция ногтевой пластины" in names


def test_stitch_is_noop_when_name_present():
    bounds, cmap = _k3_bounds_cmap()
    r1 = _row(_w("Консультация терапевта", 115, 40), _w("9000", 470, 40))
    r2 = _row(_w("Консультация хирурга", 115, 52), _w("12000", 470, 52))
    stitched = stitch_multiline([r1, r2], bounds, cmap)
    assert len(stitched) == 2
    assert assign_to_columns(stitched[0], bounds)[cmap.name_idx] == "Консультация терапевта"


def test_stitch_max_absorb_boundary():
    # T1: при достижении max_absorb лишние строки не теряются — остаются отдельно.
    bounds, cmap = _k3_bounds_cmap()
    anchor = _row(_w("кровь с ЭДТА", 390, 40), _w("880", 470, 40))
    conts = [_row(_w(f"строка{k}", 115, 50 + 10 * k)) for k in range(4)]
    stitched = stitch_multiline([anchor, *conts], bounds, cmap, max_absorb=2)
    assert assign_to_columns(stitched[0], bounds)[cmap.name_idx] == "строка0 строка1"
    # Оставшиеся две строки сохранены, не проглочены молча.
    leftover = [assign_to_columns(r, bounds)[cmap.name_idx] for r in stitched[1:]]
    assert leftover == ["строка2", "строка3"]


# --- интеграция через экстрактор (T3) ---------------------------------------


def test_extractor_read_name_strips_row_number_k4():
    # Имя «9 Выездная консультация врача» в колонке «№» -> читается без номера.
    cmap = ColumnMap(name_idx=0, code_idx=None, price_idxs=[1], name_has_index=True)
    cells = ["9 Выездная консультация врача", "148500"]
    assert PdfTextExtractor._read_name(cells, cmap) == "Выездная консультация врача"


def test_extractor_read_name_keeps_number_without_index_flag():
    # Без флага name_has_index ведущую цифру настоящего названия не трогаем.
    cmap = ColumnMap(name_idx=0, code_idx=None, price_idxs=[1], name_has_index=False)
    cells = ["3D реконструкция", "5000"]
    assert PdfTextExtractor._read_name(cells, cmap) == "3D реконструкция"


def test_scan_extractor_strips_row_number():
    # T3: та же логика среза номера в скан-экстракторе.
    from app.pipeline.extractors.pdf_scan import PdfScanExtractor

    cmap = ColumnMap(name_idx=0, code_idx=None, price_idxs=[1], name_has_index=True)
    cells = ["6 Перевязка раны", "5000"]
    assert PdfScanExtractor._extract_name(cells, cmap, "6 Перевязка раны 5000") == "Перевязка раны"


def test_stitch_preserves_both_prices_when_assembling_name():
    # T1: у реальных K3/K4 два-три тарифа — обе цены остаются при склейке имени.
    bounds = [80.0, 110.0, 315.0, 385.0, 465.0, 519.0]
    cmap = ColumnMap(name_idx=1, code_idx=2, price_idxs=[4, 5])
    anchor = _row(_w("кровь с ЭДТА", 390, 43), _w("880", 470, 43), _w("1410", 522, 43))
    name_row = _row(_w("Общий анализ крови (ОАК без СОЭ)", 115, 50))
    nxt = _row(_w("кровь с ЭДТА", 390, 57), _w("3980", 470, 57), _w("2985", 522, 57))
    stitched = stitch_multiline([anchor, name_row, nxt], bounds, cmap)
    cells = assign_to_columns(stitched[0], bounds)
    assert cells[cmap.name_idx] == "Общий анализ крови (ОАК без СОЭ)"
    assert cells[4] == "880"
    assert cells[5] == "1410"


def test_stitch_upward_stops_at_own_code_above():
    # T2: если у строки выше СВОЙ код — это отдельная услуга, вверх не тянем.
    bounds, cmap = _k3_bounds_cmap()
    prev = _row(_w("Предыдущая услуга", 115, 40), _w("В01.1", 320, 40))
    anchor = _row(_w("6", 115, 47), _w("В02.2", 320, 47), _w("880", 470, 47))
    cmap2 = ColumnMap(name_idx=1, code_idx=2, price_idxs=[4], name_has_index=True)
    stitched = stitch_multiline([prev, anchor], bounds, cmap2)
    # «6» с кодом В02.2 не должен слиться с «Предыдущая услуга» (код В01.1).
    names = [assign_to_columns(r, bounds)[cmap2.name_idx] for r in stitched]
    assert "Предыдущая услуга" in names


def test_analyze_table_then_stitch_pipeline():
    # T3: интеграция analyze_table -> stitch_multiline. Несколько обычных строк
    # задают плотность колонок, затем пустая ценовая строка добирает имя и код
    # со строки ниже (геометрия Клиники 3).
    rows = [_row(_w("Наименование", 100, 0), _w("Код", 320, 0), _w("Цена", 470, 0))]
    for k, (nm, cd, pr) in enumerate(
        [("Глюкоза", "В03.1", "1200"), ("Холестерин", "В03.2", "1300"),
         ("Креатинин", "В03.3", "1400")]
    ):
        rows.append(_row(_w(nm, 100, 20 + 12 * k), _w(cd, 320, 20 + 12 * k), _w(pr, 470, 20 + 12 * k)))
    rows.append(_row(_w("880", 470, 70)))  # пустая ценовая строка
    rows.append(_row(_w("Общий анализ крови", 100, 77), _w("В02.110", 320, 77)))
    bounds, cmap, header_idx = analyze_table(rows)
    stitched = stitch_multiline(rows[header_idx + 1:], bounds, cmap)
    merged = [assign_to_columns(r, bounds) for r in stitched if r.cells]
    assert cmap.code_idx is not None
    assert any(
        m[cmap.name_idx] == "Общий анализ крови" and m[cmap.code_idx] == "В02.110"
        for m in merged
    )


def test_is_section_heading_rejects_abbreviation_list():
    # EH-1: список аббревиатур это продолжение названия панели, не заголовок.
    assert _is_section_heading(["АЛАТ АСАТ ГГТ ЩФ"]) is False
    assert _is_section_heading(["BRCA ATM CHEK PALB"]) is False
    # Настоящий заголовок (есть длинное слово) по-прежнему ловится.
    assert _is_section_heading(["ГОРМОНЫ"]) is True
    assert _is_section_heading(["ИММУНОГЕМАТОЛОГИЧЕСКИЕ ИССЛЕДОВАНИЯ"]) is True


def test_is_document_preamble():
    assert _is_document_preamble("Приложение № 1 от 01.01.2026") is True
    assert _is_document_preamble("к договору на оказание медицинских услуг") is True
    assert _is_document_preamble("Общий анализ крови") is False


def test_strip_leading_enumeration_keeps_quantity_unit():
    # EH-4: количество перед единицей не номер строки — не срезаем.
    assert strip_leading_enumeration("2 канала корневой пломбировки") == "2 канала корневой пломбировки"
    assert strip_leading_enumeration("3 зоны лазерной эпиляции") == "3 зоны лазерной эпиляции"
    # Номер строки перед названием по-прежнему срезаем.
    assert strip_leading_enumeration("9 Выездная консультация врача") == "Выездная консультация врача"


def test_looks_like_price_leading_large_number_with_description():
    # T7: цена с описанием в одной ячейке («5000 тг аппарат»), но не номер строки.
    assert _looks_like_price("5000 тг аппарат Тонзилор") is True
    assert _looks_like_price("9 Выездная консультация врача") is False


def test_is_index_sequence_rejects_small_constant():
    # C2-nit: постоянная мелкая колонка [2,2,2] это не сквозная нумерация.
    assert _is_index_sequence([2, 2, 2, 2]) is False


def test_stitch_early_returns_without_price_or_name():
    # T4-nit: без колонки имени или цены склейка ничего не делает.
    bounds, _ = _k3_bounds_cmap()
    rows = [_row(_w("Текст", 115, 40))]
    no_name = ColumnMap(name_idx=None, price_idxs=[4])
    no_price = ColumnMap(name_idx=1, price_idxs=[])
    assert stitch_multiline(rows, bounds, no_name) is rows
    assert stitch_multiline(rows, bounds, no_price) is rows


def test_line_gap_limit_empty_fallback():
    # T6-nit: без слов берём дефолтный порог, а не падаем.
    assert _line_gap_limit([]) == 16.0
    assert _line_gap_limit([Row(words=[], top=0.0)]) == 16.0
    # С реальными словами порог = 2.2 высоты строки (>= пол).
    assert _line_gap_limit([_row(_w("Анализ", 0, 0))]) == max(10 * 2.2, 12.0)
