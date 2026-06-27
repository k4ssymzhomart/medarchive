"""Геометрия таблиц без линий разметки (раздел 7.2, ловушка 2).

Во всех PDF архива extract_tables возвращает ноль таблиц: разметка держится
на координатах слов, а не на линиях. Мы кластеризуем слова по X-координате
в колонки и группируем по Y в строки. Это ключевое инженерное отличие.

Общий вход — список Word: {text, x0, x1, top, bottom}. И pdfplumber, и
pytesseract нормализуются к этому виду, поэтому модуль переиспользуется
текстовым и сканированным PDF экстракторами.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.pipeline.price_parser import parse_amount as _parse_amount

# Якорные слова заголовка таблицы (раздел 7.2).
HEADER_ANCHORS = (
    "наименование", "услуга", "услуги", "название",
    "цена", "стоимость", "тариф", "сумма",
    "код", "шифр",
    "ед", "единица", "измерения",
    "резидент", "нерезидент", "гражданин", "иностран",
    "первичный", "повторный", "страхов",
)

# Слова-подсказки тарифных колонок -> наша семантика.
RESIDENT_HINTS = ("резидент", "граждан рк", "граждане рк", "рк", "первичный", "базов")
NONRESIDENT_HINTS = ("нерезидент", "иностран", "без гражданства", "снг", "зарубеж", "повторный")
PRICE_HINTS = ("цена", "стоимость", "тариф", "сумма", "тенге", "тг")
CODE_HINTS = ("код", "шифр", "тарификатор", "№")
NAME_HINTS = ("наименование", "услуга", "услуги", "название")


@dataclass
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float

    @property
    def xmid(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class Row:
    words: list[Word] = field(default_factory=list)
    top: float = 0.0
    # Готовые ячейки склеенной строки (stitch_multiline). Если заданы — берём их,
    # не пересобирая из words по X (слова разных уровней Y перемешались бы).
    cells: list[str] | None = None

    def text(self) -> str:
        if self.cells is not None:
            return " ".join(c for c in self.cells if c).strip()
        return " ".join(w.text for w in sorted(self.words, key=lambda w: w.x0)).strip()


def group_rows(words: list[Word], y_tol: float = 3.0) -> list[Row]:
    """Группирует слова в строки по Y-координате с допуском y_tol."""
    rows: list[Row] = []
    for w in sorted(words, key=lambda w: (round(w.top), w.x0)):
        placed = False
        for row in rows:
            if abs(row.top - w.top) <= y_tol:
                row.words.append(w)
                placed = True
                break
        if not placed:
            rows.append(Row(words=[w], top=w.top))
    rows.sort(key=lambda r: r.top)
    return rows


def cluster_columns(words: list[Word], min_gap: float = 18.0) -> list[float]:
    """Определяет границы колонок по большим горизонтальным разрывам между
    проекциями слов на ось X (gap-based). Возвращает список X-границ
    (левые края колонок)."""
    if not words:
        return []
    intervals = sorted((w.x0, w.x1) for w in words)
    # Сливаем пересекающиеся проекции в занятые отрезки.
    merged: list[list[float]] = [list(intervals[0])]
    for x0, x1 in intervals[1:]:
        if x0 <= merged[-1][1] + 1.0:
            merged[-1][1] = max(merged[-1][1], x1)
        else:
            merged.append([x0, x1])
    # Границы колонок там, где между занятыми отрезками разрыв >= min_gap.
    bounds = [merged[0][0]]
    for prev, cur in zip(merged, merged[1:]):
        if cur[0] - prev[1] >= min_gap:
            bounds.append(cur[0])
    return bounds


def assign_to_columns(row: Row, bounds: list[float]) -> list[str]:
    """Раскладывает слова строки по колонкам, заданным границами bounds.

    Для склеенной строки (stitch_multiline) ячейки уже собраны в порядке чтения
    сверху вниз и лежат в row.cells — берём их. Обычную строку раскладываем по X.
    """
    if row.cells is not None:
        return list(row.cells)
    cells = ["" for _ in bounds]
    for w in sorted(row.words, key=lambda w: w.x0):
        idx = 0
        for i, b in enumerate(bounds):
            if w.xmid >= b:
                idx = i
        cells[idx] = (cells[idx] + " " + w.text).strip()
    return cells


def find_header(rows: list[Row], max_scan: int = 25) -> int:
    """Ищет индекс строки заголовка по якорным словам. -1 если не найдена."""
    best_idx, best_score = -1, 0
    for i, row in enumerate(rows[:max_scan]):
        low = row.text().lower()
        score = sum(1 for a in HEADER_ANCHORS if a in low)
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx if best_score >= 2 else -1


@dataclass
class ColumnMap:
    """Семантика колонок: индексы в списке ячеек строки."""

    name_idx: int | None = None
    code_idx: int | None = None
    price_idxs: list[int] = field(default_factory=list)
    labels: dict[int, str] = field(default_factory=dict)  # idx -> исходная подпись
    name_has_index: bool = False  # колонка названия совмещена с номером строки «№»


# Метки колонки номера строки/кода — это не цена.
_NUMBER_COLUMN_LABELS = {"№", "n", "#", "номер", "код", "шифр", "no"}

# Валютные слова-хвосты цены: «5000 тенге», «9000 тг».
_CURRENCY_WORD = re.compile(r"тенге|тг|kzt|руб|rub|usd|₸|\$", re.IGNORECASE)


def _looks_like_price(text: str) -> bool:
    """Ячейка это цена: парсится в число, а из букв остаётся только валюта или
    короткий предлог («5000 тенге», «от 5000»). «9 Выездная консультация врача»
    ценой НЕ считается — иначе колонка названий с ведущим номером уезжает в цены."""
    if _parse_amount(text) is None:
        return False
    core = _CURRENCY_WORD.sub("", text)
    return sum(ch.isalpha() for ch in core) <= 2


def _looks_like_code(text: str) -> bool:
    """Код услуги: содержит буквы с цифрами («U1.7», «B03.328») или 2+ разделителя
    («557.002.1»). Чистое число («16600», «1.7») кодом НЕ считается — это цена."""
    t = text.strip()
    if not t or " " in t or len(t) > 24:
        return False
    has_alpha = any(ch.isalpha() for ch in t)
    has_digit = any(ch.isdigit() for ch in t)
    if not has_digit:
        return False
    if has_alpha:
        return True
    return (t.count(".") + t.count("-") + t.count("/")) >= 2


def _is_index_sequence(values: list) -> bool:
    """Колонка похожа на сквозной номер строки, а не на цену.

    Номер строки идёт целыми с шагом 1 и часто сбрасывается на 1 в начале
    нового раздела (9, 10, 1, 2, 3, ...). Цены так себя почти не ведут, поэтому
    считаем долю «шагов нумерации»: инкремент на 1, повтор или сброс к малому
    значению. Высокая доля -> это нумерация, исключаем колонку из цен."""
    ints = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return False
        if f != int(f) or f < 0 or f > 100000:
            return False
        ints.append(int(f))
    if len(ints) < 3:
        return False
    # Шаг нумерации: инкремент на 1 либо сброс к малому значению (новый раздел).
    # Постоянную колонку (одинаковые цены) индексом НЕ считаем — нет прогресса.
    enum_steps = sum(
        1 for a, b in zip(ints, ints[1:]) if b == a + 1 or (1 <= b <= 3 and b <= a)
    )
    return enum_steps / (len(ints) - 1) > 0.7


def column_bounds_by_density(
    rows: list[Row], min_gap: float = 10.0, street_frac: float = 0.08, bin_size: float = 2.0
) -> list[float]:
    """Границы колонок по плотности слов ДАННЫХ строк, а не заголовка.

    Шапки тарифных таблиц часто многострочные и физически перекрывают несколько
    числовых колонок (Клиника 4: три тарифа по гражданству), из-за чего границы
    по заголовку сливают колонки и две цены склеиваются в одно число. Здесь мы
    ищем вертикальные «улицы» пустоты по всем строкам данных: x-диапазоны,
    которые почти не покрыты словами. Это устойчиво разделяет выровненные колонки.
    """
    words = [w for r in rows for w in r.words]
    if not words:
        return []
    x_min = min(w.x0 for w in words)
    x_max = max(w.x1 for w in words)
    if x_max - x_min < bin_size:
        return [x_min]
    n_bins = int((x_max - x_min) / bin_size) + 1
    coverage = [0] * n_bins
    for r in rows:
        covered: set[int] = set()
        for w in r.words:
            b0 = max(0, int((w.x0 - x_min) / bin_size))
            b1 = min(n_bins - 1, int((w.x1 - x_min) / bin_size))
            covered.update(range(b0, b1 + 1))
        for b in covered:
            coverage[b] += 1

    threshold = max(1, int(street_frac * max(1, len(rows))))
    min_gap_bins = max(1, int(min_gap / bin_size))

    bounds = [x_min]
    in_street = False
    street_start = 0
    for b in range(n_bins):
        is_street = coverage[b] <= threshold
        if is_street and not in_street:
            in_street, street_start = True, b
        elif not is_street and in_street:
            in_street = False
            if (b - street_start) >= min_gap_bins:
                new_bound = x_min + b * bin_size
                if new_bound - bounds[-1] >= min_gap:
                    bounds.append(new_bound)
    return bounds


def infer_column_map(rows: list[Row], bounds: list[float], sample: int = 250) -> ColumnMap:
    """Определяет роли колонок по СОДЕРЖИМОМУ (когда заголовок битый/отсутствует).

    Цена это колонка, где большая доля ячеек парсится как число. Имя это колонка
    с наибольшим объёмом буквенного текста. Код это короткая колонка вида «U1.1».
    """
    n = len(bounds)
    if n == 0:
        return ColumnMap()
    counts = [0] * n
    numeric = [0] * n
    alpha_len = [0] * n
    code_like = [0] * n
    values: list[list] = [[] for _ in range(n)]
    for r in rows[:sample]:
        cells = assign_to_columns(r, bounds)
        for i in range(min(n, len(cells))):
            t = cells[i].strip()
            if not t:
                continue
            counts[i] += 1
            if _looks_like_code(t):
                code_like[i] += 1  # код важнее: «U1.7» это код, не цена
            elif _looks_like_price(t):
                numeric[i] += 1
                values[i].append(_parse_amount(t))
            else:
                alpha_len[i] += sum(ch.isalpha() for ch in t)

    # Цена: колонка с большой долей чисел, не являющаяся сквозным номером строки.
    price_idxs = []
    for i in range(n):
        if not counts[i] or numeric[i] / counts[i] <= 0.5:
            continue
        if _is_index_sequence(values[i]):
            continue
        price_idxs.append(i)

    name_idx, best = None, -1
    for i in range(n):
        if i in price_idxs:
            continue
        if alpha_len[i] > best:
            best, name_idx = alpha_len[i], i
    code_idx = None
    for i in range(n):
        if i in price_idxs or i == name_idx:
            continue
        if counts[i] and code_like[i] / counts[i] > 0.4:
            code_idx = i
            break
    labels = {idx: f"Цена {k + 1}" for k, idx in enumerate(price_idxs)}
    return ColumnMap(name_idx=name_idx, code_idx=code_idx, price_idxs=price_idxs, labels=labels)


def analyze_table(rows: list[Row]) -> tuple[list[float], ColumnMap, int]:
    """Единая точка разбора таблицы для PDF экстракторов.

    Возвращает (bounds, cmap, header_idx). Границы колонок считаются по плотности
    строк данных (устойчиво к многострочным шапкам), роли колонок берутся из
    заголовка если он найден, иначе выводятся по содержимому. Цены всегда
    позиционно по числовым колонкам, поэтому соседние тарифы не склеиваются.
    """
    header_idx = find_header(rows)
    data_rows = rows[header_idx + 1:] if header_idx >= 0 else rows
    bounds = column_bounds_by_density(data_rows)
    if len(bounds) < 2:
        # запасной путь: кластеризация по разрывам всех слов данных
        bounds = cluster_columns([w for r in data_rows for w in r.words])
    if len(bounds) < 1:
        return [], ColumnMap(), header_idx

    content = infer_column_map(data_rows, bounds)
    if header_idx >= 0:
        header_cells = assign_to_columns(rows[header_idx], bounds)
        hcmap = map_columns(header_cells)
        price_idxs = list(content.price_idxs or hcmap.price_idxs)
        # Колонку с подписью «№»/«Код» исключаем из цен и назначаем кодом.
        number_cols = {
            idx
            for idx, lbl in hcmap.labels.items()
            if (lbl or "").strip().lower() in _NUMBER_COLUMN_LABELS
        }
        price_idxs = [i for i in price_idxs if i not in number_cols]
        labels = {
            idx: (hcmap.labels.get(idx) or content.labels.get(idx) or f"Цена {k + 1}")
            for k, idx in enumerate(price_idxs)
        }
        code_idx = hcmap.code_idx if hcmap.code_idx is not None else content.code_idx
        if code_idx is None and number_cols:
            code_idx = min(number_cols)
        name_idx = hcmap.name_idx if hcmap.name_idx is not None else content.name_idx
        # Колонка «№» слилась с названием (нет зазора между номером и именем):
        # такой «код» это сквозной номер строки, не код услуги. Снимаем его с
        # роли кода и помечаем, что у названия есть ведущий номер для очистки.
        name_has_index = False
        if name_idx is not None and code_idx == name_idx:
            name_has_index = True
            code_idx = None
        cmap = ColumnMap(
            name_idx=name_idx,
            code_idx=code_idx,
            price_idxs=price_idxs,
            labels=labels,
            name_has_index=name_has_index,
        )
    else:
        cmap = content
    return bounds, cmap, header_idx


def map_columns(header_cells: list[str]) -> ColumnMap:
    """По ячейкам строки заголовка строит карту колонок (раздел 7.7)."""
    cmap = ColumnMap()
    for idx, cell in enumerate(header_cells):
        low = cell.lower().strip()
        if not low:
            continue
        cmap.labels[idx] = cell.strip()
        if any(h in low for h in NAME_HINTS) and cmap.name_idx is None:
            cmap.name_idx = idx
        elif any(h in low for h in CODE_HINTS) and cmap.code_idx is None:
            cmap.code_idx = idx
        elif any(h in low for h in PRICE_HINTS + RESIDENT_HINTS + NONRESIDENT_HINTS):
            cmap.price_idxs.append(idx)
    # Фолбэк: если имя не нашли — берём самую широкую текстовую колонку (часто это name).
    return cmap


# Ведущий номер строки в колонке названия: «9 Выездная консультация врача».
_LEADING_INDEX_RE = re.compile(r"^\s*\d{1,3}[.)]?\s+(?=\D)")


def strip_leading_enumeration(name: str) -> str:
    """Срезает ведущий номер строки у названия, когда колонка «№» слилась с
    названием (ColumnMap.name_has_index). «9 Выездная консультация врача» ->
    «Выездная консультация врача». Требуем пробел и нецифру после номера,
    чтобы не трогать настоящие названия вроде «3D реконструкция»."""
    return _LEADING_INDEX_RE.sub("", name, count=1).strip() or name


def _row_is_priced(cells: list[str], cmap: ColumnMap) -> bool:
    """В строке есть распарсенная цена хотя бы в одной тарифной колонке."""
    for idx in cmap.price_idxs:
        if idx < len(cells) and _parse_amount(cells[idx]) is not None:
            return True
    return False


def _is_bare_index(text: str) -> bool:
    """Ячейка это только номер строки: «6», «10.», «3)» — не название."""
    return re.fullmatch(r"\d{1,3}[.)]?", text.strip()) is not None


# Ключевые слова, с которых начинается строка раздела/подраздела.
_SECTION_KEYWORDS = ("раздел", "подраздел", "глава", "категория", "прейскурант")


def _is_section_heading(cells: list[str]) -> bool:
    """Заголовок раздела внутри окна склейки: текст почти весь капсом и без цифр
    («ЦИТОЛОГИЯ», «ИММУНОГЕМАТОЛОГИЧЕСКИЕ ИССЛЕДОВАНИЯ»). На нём склейку
    останавливаем. Продолжение названия НЕ заголовок: оно начинается со скобки,
    строчной буквы или знака, заканчивается знаком переноса, либо содержит цифры
    (списки антител «PML, gp21,0, LK.M-1, ...»)."""
    text = " ".join(c for c in cells if c.strip()).strip()
    if not text or text[0] in "(<[-—.,:;":
        return False
    if text[-1] in ",(/-":
        return False
    if any(ch.isdigit() for ch in text):
        return False
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 5:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    # Одно-двухсловный капсовый заголовок («ГОРМОНЫ») короче 12 символов тоже
    # заголовок, поэтому строгий капс ловим без ограничения длины.
    if upper_ratio >= 0.9:
        return True
    return upper_ratio > 0.7 and len(text) >= 12


def _is_absorb_boundary(cells: list[str], cmap: ColumnMap) -> bool:
    """Граница склейки: заголовок раздела (капс) или строка по ключевому слову
    («подраздел 1.2 ...»). Дальше этой строки название не тянем."""
    if _is_section_heading(cells):
        return True
    if cmap.name_idx is not None and cmap.name_idx < len(cells):
        return cells[cmap.name_idx].strip().lower().startswith(_SECTION_KEYWORDS)
    return False


def _name_incomplete(name: str) -> bool:
    """Название оборвано и продолжается ниже: пусто, кончается знаком переноса
    или скобка не закрыта («... (Определение натрия (Na) в»)."""
    n = name.strip()
    if not n:
        return True
    if n[-1] in "(,/":
        return True
    return n.count("(") > n.count(")")


def _anchor_needs_name(name: str, cmap: ColumnMap) -> bool:
    """Ценовой строке нужно дотянуть название: оно пустое, это голый номер строки
    (Клиника 4) или оборванный фрагмент."""
    n = name.strip()
    if not n:
        return True
    if cmap.name_has_index and _is_bare_index(n):
        return True
    return _name_incomplete(n)


def _assembled_name(
    members: list[int], cells_list: list[list[str]], cmap: ColumnMap, anchor: int
) -> str:
    """Название, собранное из колонки имени строк-членов (без голого номера)."""
    parts: list[str] = []
    for m in members:
        cells = cells_list[m]
        text = cells[cmap.name_idx].strip() if cmap.name_idx < len(cells) else ""
        if not text:
            continue
        if m == anchor and cmap.name_has_index and _is_bare_index(text):
            continue
        parts.append(text)
    return " ".join(parts)


def _merge_member_cells(
    members: list[int], cells_list: list[list[str]], cmap: ColumnMap, anchor: int
) -> list[str]:
    """Собирает ячейки склеенной строки: по каждой колонке склеивает текст всех
    строк-членов в порядке Y (members уже отсортированы сверху вниз). Голый номер
    строки в колонке названия (Клиника 4) выкидываем — это не часть имени."""
    width = max(len(cells_list[m]) for m in members)
    out = ["" for _ in range(width)]
    for col in range(width):
        parts: list[str] = []
        for m in members:
            cells = cells_list[m]
            text = cells[col].strip() if col < len(cells) else ""
            if not text:
                continue
            if (
                col == cmap.name_idx
                and m == anchor
                and cmap.name_has_index
                and _is_bare_index(text)
            ):
                continue
            parts.append(text)
        out[col] = " ".join(parts)
    return out


def stitch_multiline(
    data_rows: list[Row], bounds: list[float], cmap: ColumnMap, max_absorb: int = 10
) -> list[Row]:
    """Склейка многострочных названий услуг в одну позицию (issue #1).

    В части PDF логическая позиция разложена по нескольким строкам Y:
    - Клиника 3: ценовая строка несёт биоматериал и цену, а название (и код) идут
      строками НИЖЕ. group_rows бьёт их по Y, поэтому в имя попадал биоматериал
      («кровь с ЭДТА») вместо «Общий анализ крови (ОАК без СОЭ)».
    - Клиника 4: название обёрнуто ВОКРУГ ценовой строки (часть выше, часть ниже),
      а в самой ценовой строке стоит только номер «6».

    Ценовая строка (anchor), которой нужно дотянуть название, поглощает соседние
    строки без цены: вниз — продолжения имени/кода, вверх — если своё имя пустое
    или это голый номер. Останавливаемся на следующей ценовой строке и на границе
    раздела. Текст каждой колонки склеивается отдельно в порядке чтения, поэтому
    биоматериал и цена не попадают в имя. Ценовые строки с готовым названием не
    трогаем (Клиника 4 «Выездная консультация врача» и штатные прайсы — без
    регрессий)."""
    if cmap.name_idx is None or not cmap.price_idxs:
        return data_rows

    n = len(data_rows)
    cells_list = [assign_to_columns(r, bounds) for r in data_rows]
    priced = [_row_is_priced(c, cmap) for c in cells_list]
    boundary = [_is_absorb_boundary(c, cmap) for c in cells_list]
    claimed = [False] * n
    members_of: dict[int, list[int]] = {}

    for i in range(n):
        if not priced[i]:
            continue
        name = cells_list[i][cmap.name_idx].strip() if cmap.name_idx < len(cells_list[i]) else ""
        if not _anchor_needs_name(name, cmap):
            continue
        members = [i]
        absorbed = 0
        # Вверх тянем только когда своего имени по сути нет (Клиника 4: имя над ценой).
        if not name or (cmap.name_has_index and _is_bare_index(name)):
            j = i - 1
            while (
                j >= 0 and absorbed < max_absorb
                and not claimed[j] and not priced[j] and not boundary[j]
            ):
                members.insert(0, j)
                claimed[j] = True
                absorbed += 1
                j -= 1
        # Вниз тянем продолжения имени/кода до следующей цены или раздела.
        j = i + 1
        while (
            j < n and absorbed < max_absorb
            and not claimed[j] and not priced[j] and not boundary[j]
        ):
            cand = cells_list[j][cmap.name_idx].strip() if cmap.name_idx < len(cells_list[j]) else ""
            # Заглавная буква при уже целом названии — это начало следующей
            # позиции (имя над своей ценой), не продолжение. Дальше не тянем.
            if cand[:1].isupper():
                sofar = _assembled_name(members, cells_list, cmap, i)
                if sofar and not _name_incomplete(sofar):
                    break
            members.append(j)
            claimed[j] = True
            absorbed += 1
            j += 1
        if len(members) > 1:
            members_of[i] = members
            claimed[i] = True

    result: list[Row] = []
    for i in range(n):
        if i in members_of:
            result.append(
                Row(
                    words=list(data_rows[i].words),
                    top=data_rows[i].top,
                    cells=_merge_member_cells(members_of[i], cells_list, cmap, i),
                )
            )
        elif not claimed[i]:
            result.append(data_rows[i])
    return result
