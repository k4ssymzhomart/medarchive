"""Интеграционные тесты эндпоинтов через TestClient на тестовой БД (issue #5).

Покрывают happy path + 404/422 для услуг, партнёров, документов, очереди
несопоставленных, статистики и ручного сопоставления. Тестовая БД — SQLite
в памяти (см. conftest.py): прод-код не модифицируется, get_db подменён.
"""

from __future__ import annotations

import uuid

# --------------------------------------------------------------------------- #
# /services
# --------------------------------------------------------------------------- #


def test_list_services_happy(client, seed):
    resp = client.get("/services")
    assert resp.status_code == 200
    body = resp.json()
    names = [s["service_name"] for s in body["items"]]
    # только активные услуги
    assert "Глюкоза крови" in names
    assert "Прием терапевта первичный" in names
    assert "Устаревшая услуга" not in names
    assert body["page"]["total"] == 2


def test_list_services_filter_by_substring(client, seed):
    # ILIKE из эндпоинта. На SQLite case-insensitive только для ASCII, не для
    # кириллицы, поэтому подстрока берётся в исходном регистре ("Глюкоза").
    # На Postgres ILIKE свернул бы регистр и для кириллицы — поведение шире.
    resp = client.get("/services", params={"q": "Глюкоза"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["service_name"] == "Глюкоза крови"


def test_list_services_filter_by_category(client, seed):
    resp = client.get("/services", params={"category": "Консультации"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["category"] == "Консультации"


def test_list_services_pagination(client, seed):
    page1 = client.get("/services", params={"limit": 1, "offset": 0}).json()
    page2 = client.get("/services", params={"limit": 1, "offset": 1}).json()
    assert page1["page"]["total"] == 2
    assert len(page1["items"]) == 1
    assert len(page2["items"]) == 1
    assert page1["items"][0]["service_id"] != page2["items"][0]["service_id"]


def test_list_services_invalid_limit_422(client, seed):
    # limit > 500 нарушает Query(le=500)
    assert client.get("/services", params={"limit": 9999}).status_code == 422


def test_service_partners_happy(client, seed):
    sid = seed["service_glucose"]
    resp = client.get(f"/services/{sid}/partners")
    assert resp.status_code == 200
    rows = resp.json()
    # активные позиции глюкозы: Альфа (1500) и Бета (1800); архивная и аномалия попадают тоже,
    # т.к. is_active=True у аномалии. Проверяем минимум двух партнёров.
    partner_names = {r["partner_name"] for r in rows}
    assert "Клиника Альфа" in partner_names
    assert "Клиника Бета" in partner_names
    # сортировка по цене резидента по возрастанию
    prices = [r["price_resident_kzt"] for r in rows if r["price_resident_kzt"] is not None]
    assert prices == sorted(prices, key=lambda x: float(x))


def test_service_partners_404(client, seed):
    resp = client.get(f"/services/{uuid.uuid4()}/partners")
    assert resp.status_code == 404


def test_service_partners_invalid_uuid_422(client, seed):
    assert client.get("/services/not-a-uuid/partners").status_code == 422


# --------------------------------------------------------------------------- #
# /partners
# --------------------------------------------------------------------------- #


def test_list_partners_happy(client, seed):
    resp = client.get("/partners")
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"]["total"] == 3  # включая неактивного
    assert {p["name"] for p in body["items"]} >= {"Клиника Альфа", "Клиника Бета"}


def test_list_partners_filter_city(client, seed):
    resp = client.get("/partners", params={"city": "Астана"})
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["city"] == "Астана"


def test_list_partners_filter_active(client, seed):
    resp = client.get("/partners", params={"is_active": False})
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["is_active"] is False
    assert items[0]["name"] == "Клиника Гамма"


def test_partner_services_happy(client, seed):
    pid = seed["partner_almaty"]
    resp = client.get(f"/partners/{pid}/services")
    assert resp.status_code == 200
    body = resp.json()
    # активные позиции Альфы (исключая архивную старую версию)
    assert body["page"]["total"] == 4
    assert all(i["is_active"] for i in body["items"])


def test_partner_services_active_only_false(client, seed):
    pid = seed["partner_almaty"]
    resp = client.get(f"/partners/{pid}/services", params={"active_only": False})
    body = resp.json()
    # теперь и архивная старая версия
    assert body["page"]["total"] == 5


def test_partner_services_404(client, seed):
    resp = client.get(f"/partners/{uuid.uuid4()}/services")
    assert resp.status_code == 404


def test_price_history_happy(client, seed):
    pid = seed["partner_almaty"]
    sid = seed["service_glucose"]
    resp = client.get(f"/partners/{pid}/services/{sid}/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service_name"] == "Глюкоза крови"
    # минимум две точки: архивная (1200) и активная (1500) + аномалия привязана к глюкозе
    assert len(body["points"]) >= 2
    # отсортированы по дате по возрастанию (nullsfirst)
    dated = [p for p in body["points"] if p["effective_date"]]
    dates = [p["effective_date"] for p in dated]
    assert dates == sorted(dates)
    # pct_change посчитан хотя бы для одной точки
    assert any(p["pct_change"] is not None for p in body["points"])


def test_price_history_empty_for_unknown_pair(client, seed):
    # валидные UUID, но пары нет -> пустая история, 200
    pid = seed["partner_astana"]
    sid = seed["service_consult"]
    resp = client.get(f"/partners/{pid}/services/{sid}/history")
    assert resp.status_code == 200
    assert resp.json()["points"] == []


# --------------------------------------------------------------------------- #
# /documents
# --------------------------------------------------------------------------- #


def test_list_documents_happy(client, seed):
    resp = client.get("/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) == 2
    formats = {d["file_format"] for d in docs}
    assert formats == {"xlsx", "pdf"}


def test_list_documents_filter_status(client, seed):
    resp = client.get("/documents", params={"status": "done"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    resp_none = client.get("/documents", params={"status": "error"})
    assert resp_none.json() == []


def test_document_status_happy(client, seed):
    did = seed["doc"]
    resp = client.get(f"/documents/{did}/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["file_name"] == "alfa_price.xlsx"
    assert body["parse_status"] == "done"
    assert body["item_count"] == 4
    assert body["processing_seconds"] == 1.5


def test_document_status_404(client, seed):
    assert client.get(f"/documents/{uuid.uuid4()}/status").status_code == 404


def test_document_status_invalid_uuid_422(client, seed):
    assert client.get("/documents/bad-id/status").status_code == 422


# --------------------------------------------------------------------------- #
# /unmatched (очередь оператора)
# --------------------------------------------------------------------------- #


def test_unmatched_all(client, seed):
    resp = client.get("/unmatched")
    assert resp.status_code == 200
    body = resp.json()
    # all = unmatched ИЛИ needs_review: загадочная процедура, прием терапевта, узи (аномалия в ревью)
    raws = {i["service_name_raw"] for i in body["items"]}
    assert "загадочная процедура" in raws
    assert "прием терапевта" in raws


def test_unmatched_mode_unmatched(client, seed):
    resp = client.get("/unmatched", params={"mode": "unmatched"})
    items = resp.json()["items"]
    raws = {i["service_name_raw"] for i in items}
    assert raws == {"загадочная процедура"}


def test_unmatched_mode_needs_review(client, seed):
    resp = client.get("/unmatched", params={"mode": "needs_review"})
    items = resp.json()["items"]
    raws = {i["service_name_raw"] for i in items}
    assert "прием терапевта" in raws
    assert "узи брюшной полости" in raws
    assert "загадочная процедура" not in raws


def test_unmatched_mode_anomaly(client, seed):
    resp = client.get("/unmatched", params={"mode": "anomaly"})
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["service_name_raw"] == "узи брюшной полости"
    assert items[0]["is_anomaly"] is True


def test_unmatched_items_carry_context(client, seed):
    item = client.get("/unmatched", params={"mode": "unmatched"}).json()["items"][0]
    # обогащение контекстом из эндпоинта
    assert item["partner_name"] == "Клиника Альфа"
    assert item["document_name"] == "alfa_price.xlsx"
    assert "candidates" in item


def test_unmatched_invalid_mode_422(client, seed):
    # mode не из паттерна ^(all|unmatched|needs_review|anomaly)$
    assert client.get("/unmatched", params={"mode": "garbage"}).status_code == 422


# --------------------------------------------------------------------------- #
# /match (ручное сопоставление)
# --------------------------------------------------------------------------- #


def test_match_confirm(client, seed):
    payload = {
        "item_id": str(seed["item_unmatched"]),
        "service_id": str(seed["service_consult"]),
        "action": "confirm",
    }
    resp = client.post("/match", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["service_id"] == str(seed["service_consult"])
    assert body["match_method"] == "manual"
    assert body["is_verified"] is True
    assert body["match_confidence"] == 1.0


def test_match_reject(client, seed):
    payload = {
        "item_id": str(seed["item_review"]),
        "action": "reject",
    }
    resp = client.post("/match", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["service_id"] is None
    assert body["match_method"] == "manual"
    assert body["is_verified"] is True


def test_match_item_not_found_404(client, seed):
    payload = {
        "item_id": str(uuid.uuid4()),
        "service_id": str(seed["service_glucose"]),
        "action": "confirm",
    }
    assert client.post("/match", json=payload).status_code == 404


def test_match_confirm_without_service_422(client, seed):
    # confirm без service_id -> ValueError в сервисе -> HTTP 422
    payload = {
        "item_id": str(seed["item_unmatched"]),
        "service_id": None,
        "action": "confirm",
    }
    assert client.post("/match", json=payload).status_code == 422


def test_match_unknown_service_404(client, seed):
    payload = {
        "item_id": str(seed["item_unmatched"]),
        "service_id": str(uuid.uuid4()),
        "action": "confirm",
    }
    assert client.post("/match", json=payload).status_code == 404


def test_match_invalid_action_422(client, seed):
    # action не из паттерна ^(confirm|reject|correct)$ -> 422 на валидации схемы
    payload = {
        "item_id": str(seed["item_unmatched"]),
        "service_id": str(seed["service_glucose"]),
        "action": "delete",
    }
    assert client.post("/match", json=payload).status_code == 422


def test_match_malformed_body_422(client, seed):
    # отсутствует обязательный item_id
    assert client.post("/match", json={"action": "confirm"}).status_code == 422


# --------------------------------------------------------------------------- #
# /stats
# --------------------------------------------------------------------------- #


def test_stats_happy(client, seed):
    resp = client.get("/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["documents_total"] == 2
    assert body["partners_total"] == 3
    assert body["services_total"] == 3  # build_stats считает все услуги, включая неактивные
    assert body["documents_by_status"]["done"] == 2
    # активные позиции: 4 у Альфы + 1 у Беты = 5 (архивная неактивна)
    assert body["items_active"] == 5
    assert 0.0 <= body["match_rate"] <= 1.0
    assert body["anomaly_count"] == 1
    assert isinstance(body["by_format"], list)
    assert isinstance(body["by_partner"], list)


def test_stats_match_rate_consistent(client, seed):
    body = client.get("/stats").json()
    # match_rate = matched / active
    if body["items_active"]:
        expected = round(body["items_matched"] / body["items_active"], 4)
        assert abs(body["match_rate"] - expected) < 1e-6


def test_stats_empty_db(client):
    # без сидов — нулевые метрики, без деления на ноль
    body = client.get("/stats").json()
    assert body["documents_total"] == 0
    assert body["items_total"] == 0
    assert body["match_rate"] == 0.0
    assert body["avg_processing_seconds"] is None
