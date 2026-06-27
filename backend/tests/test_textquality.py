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
