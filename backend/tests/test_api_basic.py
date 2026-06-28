"""Базовые интеграционные тесты приложения FastAPI (issue #5).

Открытие приложения, системные эндпоинты, контракт OpenAPI и наличие маршрутов.
Не требуют БД — проверяют, что приложение поднимается и схема согласована.
"""

from __future__ import annotations

from app import __version__


def test_app_opens_root(client):
    """Корень приложения отвечает и ссылается на документацию."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "MedServicePrice API"
    assert body["version"] == __version__
    assert body["openapi"] == "/openapi.json"


def test_health(client):
    """Health-чек отдаёт статус и версию."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert "ai_enabled" in body
    assert isinstance(body["ai_enabled"], bool)


def test_openapi_schema_valid(client):
    """OpenAPI генерируется и содержит корректный заголовок и версию."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "MedServicePrice API"
    assert schema["info"]["version"] == __version__
    assert "paths" in schema and schema["paths"]


def test_openapi_documents_core_routes(client):
    """Ключевые маршруты задокументированы в OpenAPI (контракт для фронта)."""
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    expected = [
        "/search",
        "/services",
        "/partners",
        "/documents",
        "/unmatched",
        "/match",
        "/stats",
        "/upload",
    ]
    for path in expected:
        assert path in paths, f"маршрут {path} отсутствует в OpenAPI"


def test_docs_and_redoc_available(client):
    """Swagger UI и ReDoc отдаются (документация API, критерий 15%)."""
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_unknown_route_404(client):
    """Несуществующий маршрут даёт 404."""
    assert client.get("/does-not-exist").status_code == 404
