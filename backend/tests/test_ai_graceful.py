"""Graceful-degradation внешних AI-вызовов нормализации (issue #19).

Сетевая ошибка / HTTP-ошибка / битый ответ ДОЛЖНЫ возвращать None (или пропуск),
а не ронять документ — каскад тогда деградирует на лексику. Тесты не ходят в сеть
и не требуют БД: httpx замокан, БД — фейковая с промахом кэша.
"""

from __future__ import annotations

import httpx
import pytest

from app.normalization import embeddings as emb
from app.normalization import llm_arbiter as arb
from app.normalization import rerank as rr


class _FakeResult:
    def scalar_one_or_none(self):
        return None  # всегда промах кэша -> идём в сеть


class _FakeDB:
    """Минимальная сессия: промах кэша, запись — no-op."""

    def execute(self, *args, **kwargs):
        return _FakeResult()

    def add(self, *args, **kwargs):
        pass

    def flush(self):
        pass


class _FakeResp:
    def __init__(self, *, status_error: bool = False, payload: dict | None = None):
        self._status_error = status_error
        self._payload = payload or {}

    def raise_for_status(self):
        if self._status_error:
            raise httpx.HTTPError("HTTP 500")

    def json(self):
        return self._payload


def _raise_connect(*args, **kwargs):
    raise httpx.ConnectError("network down")


@pytest.fixture
def db():
    return _FakeDB()


@pytest.fixture
def with_keys(monkeypatch):
    """Ключи присутствуют — значит код пойдёт в сеть (и должен пережить сбой)."""
    monkeypatch.setattr(emb.settings, "openai_api_key", "test-openai")
    monkeypatch.setattr(rr.settings, "cohere_api_key", "test-cohere")
    monkeypatch.setattr(arb.settings, "anthropic_api_key", "test-anthropic")
    monkeypatch.delenv("LLM_ARBITER_MODEL", raising=False)
    monkeypatch.delenv("LLM_ARBITER_PROVIDER", raising=False)


# --------------------------- эмбеддинги ---------------------------


def test_embed_text_connect_error_returns_none(db, with_keys, monkeypatch):
    monkeypatch.setattr(emb.httpx, "post", _raise_connect)
    assert emb.embed_text(db, "общий анализ крови") is None


def test_embed_text_http_error_returns_none(db, with_keys, monkeypatch):
    monkeypatch.setattr(emb.httpx, "post", lambda *a, **k: _FakeResp(status_error=True))
    assert emb.embed_text(db, "общий анализ крови") is None


def test_embed_text_malformed_response_returns_none(db, with_keys, monkeypatch):
    monkeypatch.setattr(emb.httpx, "post", lambda *a, **k: _FakeResp(payload={}))
    assert emb.embed_text(db, "общий анализ крови") is None


def test_embed_text_no_key_returns_none(db, monkeypatch):
    monkeypatch.setattr(emb.settings, "openai_api_key", "")

    def _boom(*a, **k):  # сеть не должна вызываться без ключа
        raise AssertionError("сеть не должна вызываться без ключа")

    monkeypatch.setattr(emb.httpx, "post", _boom)
    assert emb.embed_text(db, "общий анализ крови") is None


def test_embed_text_success(db, with_keys, monkeypatch):
    payload = {"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]}
    monkeypatch.setattr(emb.httpx, "post", lambda *a, **k: _FakeResp(payload=payload))
    assert emb.embed_text(db, "общий анализ крови") == [0.1, 0.2, 0.3]


def test_embed_batch_network_error_skips_all(db, with_keys, monkeypatch):
    monkeypatch.setattr(emb.httpx, "post", _raise_connect)
    assert emb.embed_batch(db, ["анализ", "узи"]) == [None, None]


# --------------------------- реранк ---------------------------


def test_rerank_connect_error_returns_none(db, with_keys, monkeypatch):
    monkeypatch.setattr(rr.httpx, "post", _raise_connect)
    assert rr.rerank(db, "анализ крови", ["оак", "узи"]) is None


def test_rerank_http_error_returns_none(db, with_keys, monkeypatch):
    monkeypatch.setattr(rr.httpx, "post", lambda *a, **k: _FakeResp(status_error=True))
    assert rr.rerank(db, "анализ крови", ["оак", "узи"]) is None


def test_rerank_no_key_returns_none(db, monkeypatch):
    monkeypatch.setattr(rr.settings, "cohere_api_key", "")
    assert rr.rerank(db, "анализ крови", ["оак", "узи"]) is None


def test_rerank_success(db, with_keys, monkeypatch):
    payload = {"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}]}
    monkeypatch.setattr(rr.httpx, "post", lambda *a, **k: _FakeResp(payload=payload))
    assert rr.rerank(db, "анализ крови", ["оак", "узи"]) == [(1, 0.9), (0, 0.2)]


# --------------------------- LLM арбитр ---------------------------


def test_arbitrate_connect_error_returns_none(db, with_keys, monkeypatch):
    monkeypatch.setattr(arb.httpx, "post", _raise_connect)
    assert arb.arbitrate(db, "оак", "гематология", ["общий анализ крови"]) is None


def test_arbitrate_http_error_returns_none(db, with_keys, monkeypatch):
    monkeypatch.setattr(arb.httpx, "post", lambda *a, **k: _FakeResp(status_error=True))
    assert arb.arbitrate(db, "оак", "гематология", ["общий анализ крови"]) is None


def test_arbitrate_no_key_returns_none(db, monkeypatch):
    monkeypatch.setattr(arb.settings, "anthropic_api_key", "")
    monkeypatch.setattr(arb.settings, "openai_api_key", "")
    monkeypatch.delenv("LLM_ARBITER_MODEL", raising=False)
    assert arb.arbitrate(db, "оак", "гематология", ["общий анализ крови"]) is None


# --------------------- выбор дешёвой модели арбитра (issue #4) ---------------------


def test_arbiter_prefers_anthropic_haiku(monkeypatch):
    monkeypatch.setattr(arb.settings, "anthropic_api_key", "a")
    monkeypatch.setattr(arb.settings, "openai_api_key", "o")
    monkeypatch.delenv("LLM_ARBITER_MODEL", raising=False)
    provider, model = arb._resolve_model()
    assert provider == "anthropic"
    assert "haiku" in model.lower()
    assert "opus" not in model.lower()


def test_arbiter_falls_back_to_openai_mini(monkeypatch):
    monkeypatch.setattr(arb.settings, "anthropic_api_key", "")
    monkeypatch.setattr(arb.settings, "openai_api_key", "o")
    monkeypatch.delenv("LLM_ARBITER_MODEL", raising=False)
    provider, model = arb._resolve_model()
    assert provider == "openai"
    assert model == "gpt-4o-mini"
    assert "opus" not in model.lower()


def test_arbiter_env_override(monkeypatch):
    monkeypatch.setattr(arb.settings, "anthropic_api_key", "")
    monkeypatch.setattr(arb.settings, "openai_api_key", "o")
    monkeypatch.setenv("LLM_ARBITER_MODEL", "gpt-4o-mini")
    provider, model = arb._resolve_model()
    assert provider == "openai" and model == "gpt-4o-mini"


def test_arbiter_no_key_resolves_none(monkeypatch):
    monkeypatch.setattr(arb.settings, "anthropic_api_key", "")
    monkeypatch.setattr(arb.settings, "openai_api_key", "")
    monkeypatch.delenv("LLM_ARBITER_MODEL", raising=False)
    assert arb._resolve_model() == (None, None)


def test_arbitrate_success(db, with_keys, monkeypatch):
    text = '{"choice": 1, "confidence": 0.95, "reason": "та же услуга"}'
    payload = {"content": [{"text": text}]}
    monkeypatch.setattr(arb.httpx, "post", lambda *a, **k: _FakeResp(payload=payload))
    verdict = arb.arbitrate(db, "оак", "гематология", ["общий анализ крови"])
    assert verdict == {"choice": 1, "confidence": 0.95, "reason": "та же услуга"}
