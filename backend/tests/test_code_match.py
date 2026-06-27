"""Тесты Level 0: детерминированный матч по коду тарификатора (Задача B).

Каскад на этом уровне не обращается к БД (возврат до семантики), поэтому
тестируем с офлайн индексом LexicalIndex.from_services и db=None.
"""

import uuid

from app.models import MatchMethod
from app.normalization.cascade import MatchCascade
from app.normalization.lexical import LexicalIndex


class FakeService:
    def __init__(self, name, code, category=None, synonyms=None):
        self.service_id = uuid.uuid4()
        self.service_name = name
        self.icd_code = code
        self.category = category
        self.synonyms = synonyms or []


def _cascade(services):
    idx = LexicalIndex.from_services(services)
    return MatchCascade(db=None, lexical=idx)


def test_code_match_unique():
    svc = FakeService("Прием врача акушера гинеколога первичный", "A02.004.000")
    cascade = _cascade([svc, FakeService("Глюкоза крови", "B03.328.001")])
    out = cascade.match("любое название из прайса", code="A02.004.000")
    assert out.method == MatchMethod.code
    assert out.service_id == svc.service_id
    assert out.score >= 0.95


def test_code_match_homoglyph():
    svc = FakeService("Глюкоза сахар крови", "B06.670.012")
    cascade = _cascade([svc])
    # код из прайса с кириллической В
    out = cascade.match("Глюкоза", code="В06.670.012")
    assert out.method == MatchMethod.code
    assert out.service_id == svc.service_id


def test_code_match_ambiguous_disambiguated_by_text():
    a = FakeService("Прием терапевта первичный", "C01.001")
    b = FakeService("Прием терапевта повторный", "C01.001")
    cascade = _cascade([a, b])
    out = cascade.match("повторный прием терапевта", code="C01.001")
    assert out.method == MatchMethod.code
    assert out.score >= 0.95
    assert out.service_id == b.service_id  # текст выбрал «повторный»
    # кандидаты ограничены только услугами этого кода
    assert {c.service_id for c in out.candidates} == {a.service_id, b.service_id}


def test_unknown_code_falls_through():
    # Неизвестный код не даёт код-матч, но текстовый каскад срабатывает (exact).
    svc = FakeService("Общий анализ крови", "B03.016.002")
    cascade = _cascade([svc])
    out = cascade.match("Общий анализ крови", code="Z99.999")
    assert out.method != MatchMethod.code
    assert out.method == MatchMethod.exact
    assert out.service_id == svc.service_id
