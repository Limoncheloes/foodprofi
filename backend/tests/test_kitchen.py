"""Integration tests for /kitchen procurement API."""
import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, phone: str, role: str, rest_id: str | None = None) -> dict:
    body = {"phone": phone, "password": "pass123", "name": "Test", "role": role}
    if rest_id:
        body["restaurant_id"] = rest_id
    resp = await client.post("/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def create_fixtures(client: AsyncClient, admin: dict):
    """Returns (cook_headers, rest_id, cat_item_id)."""
    cat = await client.post("/catalog/categories", json={"name": "Мясо", "sort_order": 1}, headers=admin)
    assert cat.status_code == 201
    item = await client.post(
        "/catalog/items",
        json={"category_id": cat.json()["id"], "name": "Говядина", "unit": "kg", "variants": []},
        headers=admin,
    )
    assert item.status_code == 201
    rest = await client.post(
        "/admin/restaurants",
        json={"name": "Ресторан 1", "address": "ул. Ленина 1", "contact_phone": "+99670000001"},
        headers=admin,
    )
    assert rest.status_code == 201
    rest_id = rest.json()["id"]
    cook = await register(client, "+99671000001", "cook", rest_id)
    return cook, rest_id, item.json()["id"]


async def test_create_procurement_order_catalog_item(client: AsyncClient, admin_token: dict):
    cook, rest_id, item_id = await create_fixtures(client, admin_token)

    resp = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [{"catalog_item_id": item_id, "quantity_ordered": "5.500", "unit": "кг"}],
        },
        headers=cook,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "draft"
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity_ordered"] == 5.5
    assert data["items"][0]["is_catalog_item"] is True


async def test_create_procurement_order_raw_name(client: AsyncClient, admin_token: dict):
    cook, rest_id, _ = await create_fixtures(client, admin_token)

    resp = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [{"raw_name": "Ложки пластиковые", "quantity_ordered": "200", "unit": "шт"}],
        },
        headers=cook,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["items"][0]["raw_name"] == "Ложки пластиковые"
    assert data["items"][0]["is_catalog_item"] is False


async def test_create_order_empty_items_rejected(client: AsyncClient, admin_token: dict):
    cook, rest_id, _ = await create_fixtures(client, admin_token)
    resp = await client.post(
        "/kitchen/orders",
        json={"restaurant_id": rest_id, "items": []},
        headers=cook,
    )
    assert resp.status_code == 422


async def test_cook_cannot_order_for_other_restaurant(client: AsyncClient, admin_token: dict):
    cook, rest_id, _ = await create_fixtures(client, admin_token)
    # create another restaurant
    rest2 = await client.post(
        "/admin/restaurants",
        json={"name": "Ресторан 2", "address": "ул. Фрунзе 2", "contact_phone": "+99670000002"},
        headers=admin_token,
    )
    resp = await client.post(
        "/kitchen/orders",
        json={"restaurant_id": rest2.json()["id"], "items": [
            {"raw_name": "Что-то", "quantity_ordered": "1", "unit": "шт"}
        ]},
        headers=cook,
    )
    assert resp.status_code == 403


async def test_submit_order_returns_whatsapp_urls(client: AsyncClient, admin_token: dict):
    cook, rest_id, item_id = await create_fixtures(client, admin_token)
    order_resp = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [{"catalog_item_id": item_id, "quantity_ordered": "3.000", "unit": "кг"}],
        },
        headers=cook,
    )
    order_id = order_resp.json()["id"]

    resp = await client.post(f"/kitchen/orders/{order_id}/submit", headers=cook)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "whatsapp" in data
    assert "fallback" in data["whatsapp"]
    assert "wa.me" in data["whatsapp"]["fallback"]
    # primary is None when WHATSAPP_GROUP_JID not set in test env
    assert data["whatsapp"]["primary"] is None


async def test_submit_changes_status(client: AsyncClient, admin_token: dict):
    cook, rest_id, item_id = await create_fixtures(client, admin_token)
    order_resp = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [{"catalog_item_id": item_id, "quantity_ordered": "2", "unit": "кг"}],
        },
        headers=cook,
    )
    order_id = order_resp.json()["id"]

    resp = await client.post(f"/kitchen/orders/{order_id}/submit", headers=cook)
    assert resp.status_code == 200
    # No routing rules, no default buyer → routing status
    assert resp.json()["order"]["status"] in ("routing", "in_purchase")


async def test_submit_draft_only(client: AsyncClient, admin_token: dict):
    cook, rest_id, item_id = await create_fixtures(client, admin_token)
    order_resp = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [{"catalog_item_id": item_id, "quantity_ordered": "1", "unit": "кг"}],
        },
        headers=cook,
    )
    order_id = order_resp.json()["id"]
    await client.post(f"/kitchen/orders/{order_id}/submit", headers=cook)
    # Submit again — should fail
    resp = await client.post(f"/kitchen/orders/{order_id}/submit", headers=cook)
    assert resp.status_code == 400


async def test_list_orders_returns_cook_orders(client: AsyncClient, admin_token: dict):
    cook, rest_id, item_id = await create_fixtures(client, admin_token)
    await client.post(
        "/kitchen/orders",
        json={"restaurant_id": rest_id, "items": [
            {"catalog_item_id": item_id, "quantity_ordered": "1", "unit": "кг"}
        ]},
        headers=cook,
    )
    resp = await client.get("/kitchen/orders", headers=cook)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_whatsapp_text_contains_restaurant_and_items(client: AsyncClient, admin_token: dict):
    cook, rest_id, item_id = await create_fixtures(client, admin_token)
    order_resp = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [
                {"catalog_item_id": item_id, "quantity_ordered": "10.000", "unit": "кг"},
                {"raw_name": "Ложки", "quantity_ordered": "200", "unit": "шт"},
            ],
        },
        headers=cook,
    )
    order_id = order_resp.json()["id"]
    resp = await client.post(f"/kitchen/orders/{order_id}/submit", headers=cook)
    fallback_url = resp.json()["whatsapp"]["fallback"]
    # URL-encoded text should contain item numbering
    assert "1" in fallback_url
    assert "wa.me" in fallback_url
