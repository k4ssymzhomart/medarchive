"""Тесты геометрии колонок без линий разметки (раздел 7.2)."""

from app.pipeline.columns import (
    Word,
    assign_to_columns,
    cluster_columns,
    find_header,
    group_rows,
    map_columns,
)


def _word(text, x0, top):
    return Word(text=text, x0=x0, x1=x0 + 10 * len(text), top=top, bottom=top + 10)


def test_group_rows_by_y():
    words = [
        _word("Код", 0, 100),
        _word("Наименование", 100, 100),
        _word("Цена", 400, 100),
        _word("A1", 0, 120),
        _word("Анализ", 100, 120),
        _word("1780", 400, 120),
    ]
    rows = group_rows(words, y_tol=3)
    assert len(rows) == 2
    assert "Наименование" in rows[0].text()


def test_cluster_columns_gap_based():
    words = [
        _word("Код", 0, 100),
        _word("Наименование", 200, 100),
        _word("Цена", 600, 100),
    ]
    bounds = cluster_columns(words, min_gap=18)
    assert len(bounds) == 3


def test_find_header_and_map_columns():
    words = [
        _word("Код", 0, 100),
        _word("Наименование", 200, 100),
        _word("Цена", 600, 100),
        _word("U1", 0, 120),
        _word("Консультация", 200, 120),
        _word("5000", 600, 120),
    ]
    rows = group_rows(words)
    h = find_header(rows)
    assert h == 0
    bounds = cluster_columns(rows[h].words)
    cells = assign_to_columns(rows[h], bounds)
    cmap = map_columns(cells)
    assert cmap.code_idx is not None
    assert cmap.name_idx is not None
    assert len(cmap.price_idxs) >= 1
