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
    """Ячейка это цена. Чистое число с валютным хвостом — цена («5000 тенге»).
    Число с описанием тоже цена, если КРУПНОЕ число идёт первым («5000 тг аппарат
    Тонзилор»). «9 Выездная консультация врача» ценой НЕ считается: ведущий «9» это
    номер строки, иначе колонка названий уезжает в цены."""
    if _parse_amount(text) is None:
        return False
    core = _CURRENCY_WORD.sub("", text)
    if sum(ch.isalpha() for ch in core) <= 2:
        return True
    lead = re.match(r"\s*(\d[\d\s.,]*)", text)
    if lead:
        amount = _parse_amount(lead.group(1))
        if amount is not None and amount >= 100:
            return True
    return False


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
    # Шаг нумерации: инкремент на 1 либо сброс ВНИЗ к малому значению (новый
    # раздел). Постоянную колонку ([2,2,2], одинаковые цены) индексом НЕ считаем —
    # в ней нет прогресса.
    enum_steps = sum(
        1 for a, b in zip(ints, ints[1:]) if b == a + 1 or (1 <= b <= 3 and b < a)
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
    # «Мягкий» учёт: любая ячейка с распарсенным числом. Нужен как запасной путь
    # для вырожденных прайсов, где имя и цена слиты в одну ячейку (Клиника 5).
    numeric_loose = [0] * n
    values_loose: list[list] = [[] for _ in range(n)]
    for r in rows[:sample]:
        cells = assign_to_columns(r, bounds)
        for i in range(min(n, len(cells))):
            t = cells[i].strip()
            if not t:
                continue
            counts[i] += 1
            amount = _parse_amount(t)
            if _looks_like_code(t):
                code_like[i] += 1  # код важнее: «U1.7» это код, не цена
            elif _looks_like_price(t):
                numeric[i] += 1
                values[i].append(amount)
            else:
                alpha_len[i] += sum(ch.isalpha() for ch in t)
            if amount is not None:
                numeric_loose[i] += 1
                values_loose[i].append(amount)

    # Цена: колонка с большой долей чисел, не являющаяся сквозным номером строки.
    price_idxs = []
    for i in range(n):
        if not counts[i] or numeric[i] / counts[i] <= 0.5:
            continue
        if _is_index_sequence(values[i]):
            continue
        price_idxs.append(i)
    # Запасной путь: ни одна колонка не прошла строгий тест цены (имя и цена слиты,
    # Клиника 5). Берём по мягкому тесту, чтобы не потерять страницу целиком.
    if not price_idxs:
        for i in range(n):
            if not counts[i] or numeric_loose[i] / counts[i] <= 0.5:
                continue
            if _is_index_sequence(values_loose[i]):
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
        # Заголовок «№» может быть битым OCR (Клиника 4, стр. 9/15): определяем
        # ведущий номер по содержимому колонки названия, а не только по подписи.
        if not name_has_index and _name_column_has_indices(data_rows, bounds, name_idx):
            name_has_index = True
        cmap = ColumnMap(
            name_idx=name_idx,
            code_idx=code_idx,
            price_idxs=price_idxs,
            labels=labels,
            name_has_index=name_has_index,
        )
    else:
        cmap = content
        if _name_column_has_indices(data_rows, bounds, cmap.name_idx):
            cmap.name_has_index = True
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
# Единицы количества: «2 канала», «3 зоны» — число это часть названия, не номер.
_QUANTITY_UNITS = (
    "канал", "зон", "сеанс", "фракц", "проекц", "сустав", "сегмент",
    "поле", "точк", "зуб", "ед.", "шт", "штук",
)


def strip_leading_enumeration(name: str) -> str:
    """Срезает ведущий номер строки у названия, когда колонка «№» слилась с
    названием (ColumnMap.name_has_index). «9 Выездная консультация врача» ->
    «Выездная консультация врача». Требуем пробел и нецифру после номера, чтобы не
    трогать «3D реконструкция»; не трогаем количество перед единицей («2 канала»)."""
    match = _LEADING_INDEX_RE.match(name)
    if not match:
        return name
    rest = name[match.end():]
    first_word = rest.split(maxsplit=1)[0].lower() if rest.split() else ""
    if first_word.startswith(_QUANTITY_UNITS):
        return name
    return rest.strip() or name


def _row_is_priced(cells: list[str], cmap: ColumnMap) -> bool:
    """В строке есть распарсенная цена хотя бы в одной тарифной колонке."""
    for idx in cmap.price_idxs:
        if idx < len(cells) and _parse_amount(cells[idx]) is not None:
            return True
    return False


def _is_bare_index(text: str) -> bool:
    """Ячейка это только номер строки: «6», «10.», «3)» — не название."""
    return re.fullmatch(r"\d{1,3}[.)]?", text.strip()) is not None


# Ключевые слова и шаблоны строк-разделов и преамбулы документа (не услуги).
_SECTION_KEYWORDS = (
    "раздел", "подраздел", "глава", "категория", "прейскурант", "приложение",
)
_CONTRACT_DATE_RE = re.compile(r"\d{2}[.,]\d{2}[.,]\d{4}")


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
    # Список аббревиатур («АЛАТ АСАТ ГГТ ЩФ», «BRCA ATM CHEK») это продолжение
    # названия панели, а не заголовок: в нём нет ни одного длинного слова.
    words = [w for w in text.split() if any(ch.isalpha() for ch in w)]
    if len(words) > 1 and not any(len(w) >= 6 for w in words):
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    # Одно-двухсловный капсовый заголовок («ГОРМОНЫ») короче 12 символов тоже
    # заголовок, поэтому строгий капс ловим без ограничения длины.
    if upper_ratio >= 0.9:
        return True
    return upper_ratio > 0.7 and len(text) >= 12


def _is_document_preamble(text: str) -> bool:
    """Преамбула документа, а не услуга: «Приложение № 1 ... к договору ... от
    01.01.2026». Такие строки не часть названия и не позиция прайса."""
    low = text.lower()
    if low.startswith(_SECTION_KEYWORDS) or "договор" in low:
        return True
    return bool(_CONTRACT_DATE_RE.search(text))


def _is_absorb_boundary(cells: list[str]) -> bool:
    """Граница склейки: заголовок раздела (капс), строка-раздел по ключевому слову
    («подраздел 1.2 ...») или преамбула договора. Дальше неё название не тянем."""
    if _is_section_heading(cells):
        return True
    return _is_document_preamble(" ".join(c for c in cells if c.strip()).strip())


def _name_column_has_indices(
    rows: list[Row], bounds: list[float], name_idx: int | None, sample: int = 150
) -> bool:
    """Колонка названия начинается со сквозного номера строки («9 Выездная ...»,
    «6»). Определяем по содержимому, чтобы покрыть страницы с битым OCR заголовка
    «№» (Клиника 4, стр. 9/15), где подпись колонки не распозналась."""
    if name_idx is None:
        return False
    indexed = total = 0
    for r in rows[:sample]:
        cells = assign_to_columns(r, bounds)
        if name_idx >= len(cells):
            continue
        text = cells[name_idx].strip()
        if not text:
            continue
        total += 1
        if _is_bare_index(text) or _LEADING_INDEX_RE.match(text):
            indexed += 1
    return total >= 5 and indexed / total > 0.5


def _anchor_needs_name(name: str, cmap: ColumnMap) -> bool:
    """Ценовой строке нужно дотянуть название: оно пустое или это голый номер
    строки (Клиника 4). Частично заполненные имена не трогаем — их склейка давала
    над-поглощение (захват чужих услуг и преамбулы)."""
    n = name.strip()
    if not n:
        return True
    return cmap.name_has_index and _is_bare_index(n)


def _name_incomplete(name: str) -> bool:
    """Название оборвано и продолжается ниже: пусто, кончается знаком переноса или
    скобка не закрыта («Антитела ... (АМА-М2, М2-ЗЕ,»). Используется, чтобы
    отличить продолжение капсом (список антител) от начала следующей услуги."""
    n = name.strip()
    if not n:
        return True
    if n[-1] in "(,/":
        return True
    return n.count("(") > n.count(")")


def _line_gap_limit(rows: list[Row]) -> float:
    """Порог вертикального зазора «своя строка vs новая запись». Берём 2.2 высоты
    строки: внутри одной позиции строки идут вплотную (~1 высота), между записями
    и до преамбулы зазор заметно больше."""
    heights = sorted(w.bottom - w.top for r in rows for w in r.words if w.bottom > w.top)
    if not heights:
        return 16.0
    return max(heights[len(heights) // 2] * 2.2, 12.0)


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


# Сколько строк максимум тянем ВВЕРХ (имя над ценой): реальная обёртка это 1-2
# строки, дальше идёт шапка/преамбула.
_UPWARD_MAX_STEPS = 3


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

    Ценовая строка (anchor) с пустым/номерным именем поглощает соседние строки без
    цены — вниз продолжения имени/кода, вверх (жёстко ограниченно) имя над ценой.
    Склейка КОНСЕРВАТИВНА, чтобы не слить разные услуги и не утянуть преамбулу:
    останавливаемся на следующей ценовой строке, заголовке раздела, преамбуле, при
    большом вертикальном зазоре, на втором коде (вторая услуга) и на заглавной
    букве уже после набранного имени (начало следующей услуги). Каждая колонка
    склеивается отдельно в порядке чтения — биоматериал и цена в имя не попадают.
    Строки с готовым названием не трогаем (Клиника 4 «Выездная консультация врача»
    и штатные прайсы — без регрессий)."""
    if cmap.name_idx is None or not cmap.price_idxs:
        return data_rows

    n = len(data_rows)
    cells_list = [assign_to_columns(r, bounds) for r in data_rows]
    priced = [_row_is_priced(c, cmap) for c in cells_list]
    boundary = [_is_absorb_boundary(c) for c in cells_list]
    gap_limit = _line_gap_limit(data_rows)
    claimed = [False] * n
    members_of: dict[int, list[int]] = {}

    def name_at(k: int) -> str:
        cells = cells_list[k]
        return cells[cmap.name_idx].strip() if cmap.name_idx < len(cells) else ""

    def code_at(k: int) -> str:
        if cmap.code_idx is None or cmap.code_idx >= len(cells_list[k]):
            return ""
        return cells_list[k][cmap.code_idx].strip()

    for i in range(n):
        if not priced[i]:
            continue
        if not _anchor_needs_name(name_at(i), cmap):
            continue
        members = [i]
        name = name_at(i)
        have_name = bool(name) and not (cmap.name_has_index and _is_bare_index(name))
        have_code = bool(code_at(i))
        # Вверх: имя над ценой (Клиника 4 wrap, гистология Клиники 1). Жёстко
        # ограничиваем шагами и зазором, чтобы не утянуть шапку/преамбулу.
        steps, j = 0, i - 1
        while (
            j >= 0 and steps < _UPWARD_MAX_STEPS and len(members) <= max_absorb
            and not claimed[j] and not priced[j] and not boundary[j]
            and data_rows[j + 1].top - data_rows[j].top <= gap_limit
        ):
            if have_code and code_at(j):
                break  # своя пара «код» выше — это отдельная услуга
            members.insert(0, j)
            claimed[j] = True
            have_name = have_name or bool(name_at(j))
            have_code = have_code or bool(code_at(j))
            steps += 1
            j -= 1
        # Вниз: продолжения имени/кода до конца записи.
        j = i + 1
        while (
            j < n and len(members) <= max_absorb
            and not claimed[j] and not priced[j] and not boundary[j]
            and data_rows[j].top - data_rows[j - 1].top <= gap_limit
        ):
            cand_name, cand_code = name_at(j), code_at(j)
            if have_code and cand_code:
                break  # второй код — следующая услуга
            # Заглавная буква при УЖЕ ЦЕЛОМ имени — начало следующей услуги.
            # Если имя ещё оборвано (незакрытая скобка), капсовый фрагмент это его
            # продолжение (список антител «PML, gp21,0, ...»), тянем дальше.
            if have_name and cand_name[:1].isupper():
                sofar = _merge_member_cells(members, cells_list, cmap, i)[cmap.name_idx]
                if sofar and not _name_incomplete(sofar):
                    break
            members.append(j)
            claimed[j] = True
            have_name = have_name or bool(cand_name)
            have_code = have_code or bool(cand_code)
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
