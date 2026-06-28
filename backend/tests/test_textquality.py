"""Тесты детектора качества текстового слоя (раздел 7.1, 7.3)."""

from app.pipeline.textquality import assess_text, page_needs_ocr


def test_clean_russian_text_is_ok():
    txt = (
        "Наименование услуги Цена тенге\n"
        "Консультация врача терапевта 5000\n"
        "Общий анализ крови 1780 Стоимость\n"
        "Раздел Гематология"
    )
    q = assess_text(txt)
    assert not q.is_corrupt
    assert q.cyrillic_ratio > 0.8
    assert q.anchor_hits >= 2


def test_empty_text_is_corrupt():
    assert assess_text("").is_corrupt
    assert page_needs_ocr("")


def test_latin_gibberish_is_corrupt():
    txt = "yc.iv! Yliliepiia.i qwerty asdf zxcv jklm uiop"
    q = assess_text(txt)
    assert q.is_corrupt


def test_mixed_contamination_flagged():
    # высокая загрязнённость латиницей внутри русских слов, мало якорей
    txt = "Прейскурaнт цeн нa услугu клuнuкu пацuент"
    q = assess_text(txt)
    assert q.contamination > 0.0


# --------------------------------------------------------------------------- #
# Калибровка порога переOCR (issue #2).
#
# Детектор намеренно НЕ гонит на переOCR страницу, где битая только шапка
# («Yliliepiia.i», «Прейскурант иен»), а строки услуг читаемы: переOCR заменил
# бы пригодный текстовый слой потенциально худшим OCR. На реальном архиве слой
# Клиник 2/3 именно такой — данные извлеклись из слоя (см. docs_report/
# QUALITY_REPORT.md), поэтому порог понижать нельзя. Эти тесты фиксируют
# калибровку и страхуют от регрессии, которая начала бы переOCR-ить чистые
# страницы. Само исполнение переOCR (Tesseract) проверяется в Docker.
# --------------------------------------------------------------------------- #
def test_garbled_header_alone_is_corrupt_via_short_text():
    # Битая шапка сама по себе короткая -> правило «мало текста» (< 40 символов).
    assert assess_text("Yliliepiia.i").is_corrupt
    assert assess_text("Прейскурант иен").is_corrupt


def test_garbled_header_but_clean_rows_is_not_corrupt():
    # Шапка битая, строки услуг читаемы -> слой пригоден, переOCR не нужен.
    txt = (
        "Yliliepiia.i иен\n"
        "Консультация врача терапевта 5000\n"
        "Общий анализ крови 1780\n"
        "Биохимия крови 3200\n"
        "УЗИ брюшной полости 7000\n"
    )
    q = assess_text(txt)
    assert q.is_corrupt is False
    assert q.cyrillic_ratio > 0.8


def test_garbled_data_rows_trigger_reocr():
    # Битая не только шапка, но и сами строки услуг -> слой негоден, на переOCR.
    txt = (
        "Yliliepiia.i иен\n"
        "Koнcyльтaцuя вpaчa 5000\n"
        "Oбщuй aнaлuз кpoвu 1780\n"
        "Бuoxuмuя кpoвu 3200\n"
    )
    assert assess_text(txt).is_corrupt


def test_page_needs_ocr_tracks_assess_verdict():
    txt = "Koнcyльтaцuя вpaчa Oбщuй aнaлuз кpoвu Бuoxuмuя кpoвu"
    assert page_needs_ocr(txt) is assess_text(txt).is_corrupt
