"""Аутентификация оператора на админских эндпоинтах (issue #9, раздел 4.2).

При заданном OPERATOR_TOKEN админские эндпоинты (загрузка/документы и очередь
оператора с ручным сопоставлением) требуют Authorization: Bearer <token>, а
публичные (поиск, партнёры, услуги, статистика) остаются открытыми. При пустом
токене защита выключена — это покрыто остальным набором (он ходит без токена).
"""

from __future__ import annotations

import uuid

import pytest

from app.config import Settings, get_settings

TOKEN = "test-operator-token-secret"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture()
def auth_client(client):
    """client с включённой защитой: get_settings отдаёт настройки с токеном."""
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(operator_token=TOKEN)
    yield client
    app.dependency_overrides.pop(get_settings, None)


# --------------------------------------------------------------------------- #
# Защита включена: админские эндпоинты требуют токен.
# --------------------------------------------------------------------------- #
def test_admin_queue_without_token_401(auth_client):
    assert auth_client.get("/unmatched").status_code == 401


def test_admin_documents_without_token_401(auth_client):
    assert auth_client.get("/documents").status_code == 401


def test_admin_wrong_token_401(auth_client):
    resp = auth_client.get("/unmatched", headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 401


def test_admin_non_bearer_scheme_401(auth_client):
    # HTTPBearer(auto_error=False) нормализует не-Bearer схему в None, поэтому
    # запрос попадает в ту же ветку, что и отсутствие заголовка -> 401.
    resp = auth_client.get("/unmatched", headers={"Authorization": f"Basic {TOKEN}"})
    assert resp.status_code == 401


def test_admin_upload_without_token_401(auth_client):
    # /upload явно назван админским в критерии #9: реальный POST без токена -> 401.
    files = {"file": ("price.txt", b"x", "text/plain")}
    assert auth_client.post("/upload", files=files).status_code == 401


def test_admin_correct_token_200(auth_client):
    resp = auth_client.get("/unmatched", headers=AUTH)
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_match_without_token_401(auth_client):
    # Тело валидно по схеме: 401 от защиты, а не 422 от валидации.
    payload = {"item_id": str(uuid.uuid4()), "action": "reject"}
    assert auth_client.post("/match", json=payload).status_code == 401


def test_match_with_token_passes_auth(auth_client):
    # С токеном защита пропускает; дальше позиция не найдена -> 404 (не 401).
    payload = {"item_id": str(uuid.uuid4()), "action": "reject"}
    assert auth_client.post("/match", json=payload, headers=AUTH).status_code == 404


# --------------------------------------------------------------------------- #
# Публичные эндпоинты открыты даже при включённой защите и без токена.
# --------------------------------------------------------------------------- #
def test_public_partners_open_without_token(auth_client):
    assert auth_client.get("/partners").status_code == 200


def test_public_services_open_without_token(auth_client):
    assert auth_client.get("/services").status_code == 200


def test_public_stats_open_without_token(auth_client):
    assert auth_client.get("/stats").status_code == 200


# --------------------------------------------------------------------------- #
# Защита выключена (токен не задан): админские эндпоинты открыты.
# --------------------------------------------------------------------------- #
def test_admin_open_when_token_unset(client):
    # Фикстура client не задаёт OPERATOR_TOKEN -> dev-контур, очередь открыта.
    assert client.get("/unmatched").status_code == 200


# --------------------------------------------------------------------------- #
# Разделение public/admin зафиксировано в самой OpenAPI-схеме.
# --------------------------------------------------------------------------- #
def test_openapi_marks_admin_paths_secured(client):
    paths = client.get("/openapi.json").json()["paths"]

    def secured(path: str, method: str) -> bool:
        return bool(paths[path][method].get("security"))

    # Админские эндпоинты требуют токен.
    assert secured("/upload", "post")
    assert secured("/match", "post")
    assert secured("/unmatched", "get")
    assert secured("/documents", "get")
    # Публичные — без требования безопасности.
    assert not secured("/search", "get")
    assert not secured("/partners", "get")
    assert not secured("/services", "get")
    assert not secured("/stats", "get")
