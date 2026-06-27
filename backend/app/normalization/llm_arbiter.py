"""LLM арбитр (раздел 5.1, 8.2 уровень 5).

Только для пограничной зоны. На вход исходное название, категория и топ 3
кандидата справочника. На выход выбор кандидата (или «нет совпадения») и
короткое обоснование, которое мы пишем в verification_note. Кэш в БД.

Это ДОРОГОЙ слой точности, поэтому модель всегда ДЕШЁВАЯ (issue #4): провайдер
выбирается по доступному ключу — Anthropic Haiku или OpenAI gpt-4o-mini, никогда
не opus. Переопределяется переменными LLM_ARBITER_MODEL / LLM_ARBITER_PROVIDER.
Без ключа или при сбое сети возвращаем None — позиция уходит в needs_review.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AICache

log = logging.getLogger(__name__)

# Любой сбой сети/ответа AI = позиция уходит в needs_review (issue #19).
_AI_ERRORS = (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError)

# Дешёвые модели по умолчанию для дорогого слоя арбитра (issue #4, не opus).
_DEFAULT_ANTHROPIC = "claude-3-5-haiku-latest"
_DEFAULT_OPENAI = "gpt-4o-mini"

# Накопитель использования токенов для отчёта о стоимости (issue #4).
# Лок: verdict_for может вызываться из нескольких потоков (пред-прогрев кэша).
_usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
_usage_lock = threading.Lock()

_SYSTEM = (
    "Ты медицинский эксперт по нормализации названий услуг. Тебе дают исходное "
    "название услуги из прайса клиники и пронумерованный список кандидатов из "
    "справочника. Выбери НОМЕР единственного кандидата, который означает ту же "
    "услугу, либо 0 если совпадения нет. Ответь строго JSON: "
    '{"choice": <int>, "confidence": <0..1>, "reason": "<коротко по-русски>"}.'
)


def reset_usage() -> None:
    _usage.update(calls=0, prompt_tokens=0, completion_tokens=0)


def get_usage() -> dict:
    return dict(_usage)


def _resolve_model() -> tuple[str | None, str | None]:
    """(provider, model). Дешёвая модель по доступному ключу. Никогда не opus."""
    model = os.getenv("LLM_ARBITER_MODEL")
    provider = os.getenv("LLM_ARBITER_PROVIDER")
    if model:
        if not provider:
            provider = "openai" if model.startswith(("gpt", "o1", "o3", "o4")) else "anthropic"
        return provider, model
    if settings.anthropic_api_key:
        return "anthropic", _DEFAULT_ANTHROPIC
    if settings.openai_api_key:
        return "openai", _DEFAULT_OPENAI
    return None, None


def _key(model: str, query: str, candidates: list[str]) -> str:
    raw = "llm:" + model + ":" + query + "::" + "||".join(candidates)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _call_anthropic(model: str, prompt: str) -> str:
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 300,
            "system": _SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=45.0,
    )
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage", {})
    _account(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
    return data["content"][0]["text"]


def _call_openai(model: str, prompt: str) -> str:
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json={
            "model": model,
            "max_tokens": 300,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=45.0,
    )
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage", {})
    _account(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    return data["choices"][0]["message"]["content"]


def _account(prompt_tokens: int, completion_tokens: int) -> None:
    with _usage_lock:
        _usage["calls"] += 1
        _usage["prompt_tokens"] += int(prompt_tokens or 0)
        _usage["completion_tokens"] += int(completion_tokens or 0)


def _build_prompt(query: str, category: str | None, candidates: list[str]) -> str:
    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(candidates))
    return (
        f"Исходное название: {query}\n"
        f"Категория: {category or 'неизвестно'}\n"
        f"Кандидаты:\n{numbered}\n\nОтвет JSON:"
    )


def cache_key(query: str, candidates: list[str]) -> str | None:
    """Ключ кэша вердикта для (query, candidates) при текущей модели. None если нет ключа."""
    _provider, model = _resolve_model()
    if model is None:
        return None
    return _key(model, query, candidates)


def verdict_for(query: str, category: str | None, candidates: list[str]) -> dict | None:
    """ЧИСТЫЙ вызов арбитра БЕЗ БД: модель -> промпт -> API -> разбор JSON.

    Потокобезопасен (не трогает сессию), поэтому годится для конкурентного
    пред-прогрева кэша. None при отсутствии ключа или сбое сети.
    """
    if not candidates:
        return None
    provider, model = _resolve_model()
    if provider is None:
        return None
    prompt = _build_prompt(query, category, candidates)
    try:
        text = _call_anthropic(model, prompt) if provider == "anthropic" else _call_openai(model, prompt)
    except _AI_ERRORS as exc:
        log.warning("LLM арбитр недоступен (%s): %s", provider, exc)
        return None
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return {"choice": 0, "confidence": 0.0, "reason": "LLM вернул неразборчивый ответ"}


def arbitrate(db: Session, query: str, category: str | None, candidates: list[str]) -> dict | None:
    """Возвращает {choice:int(1-based,0=нет), confidence:float, reason:str} или None."""
    if not candidates:
        return None
    key = cache_key(query, candidates)
    if key is None:
        return None  # нет ключа -> позиция в needs_review
    row = db.execute(select(AICache).where(AICache.cache_key == key)).scalar_one_or_none()
    if row:
        return row.payload

    payload = verdict_for(query, category, candidates)
    if payload is None:
        return None
    db.add(AICache(kind="llm", cache_key=key, payload=payload))
    db.flush()
    return payload
