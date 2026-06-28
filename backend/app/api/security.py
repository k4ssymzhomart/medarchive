"""Аутентификация оператора для админских эндпоинтов (раздел 4.2).

Простая bearer-схема для MVP: единый операторский токен из OPERATOR_TOKEN.
Защищаются операции загрузки, сопоставления и очереди оператора; поиск и
страницы партнёров остаются публичными.

Если токен не задан (локальная разработка, тесты) — защита выключена, чтобы
не ломать открытый dev-контур и CI без секретов. В проде токен задаётся
секретом, и админские эндпоинты требуют заголовок Authorization: Bearer <token>.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

# auto_error=False: требовать ли токен, решаем сами (зависит от конфигурации).
_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="OperatorToken",
    description="Операторский токен из OPERATOR_TOKEN (Authorization: Bearer <token>)",
)


def require_operator(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    """Пропускает запрос только с верным операторским токеном.

    - токен не задан -> защита выключена (открытый dev-контур);
    - токен задан -> обязателен Authorization: Bearer <operator_token>.
    """
    # .strip() — частый случай: токен из секрет-менеджера приходит с хвостовым
    # переводом строки, иначе верный на вид токен давал бы 401.
    token = (settings.operator_token or "").strip()
    if not token:
        return
    # HTTPBearer(auto_error=False) уже отдаёт None для не-Bearer схемы, так что
    # ветка ниже срабатывает на отсутствии заголовка.
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется операторский токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Сравнение в постоянное время по байтам: не утекает длина/префикс токена и
    # не падает с TypeError на не-ASCII значениях (compare_digest по str — ASCII-only).
    expected = token.encode("utf-8")
    provided = credentials.credentials.encode("utf-8")
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный операторский токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
