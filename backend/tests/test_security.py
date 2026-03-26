import pytest
import pytest_asyncio
from httpx import AsyncClient


async def register(client: AsyncClient, phone: str, role: str,
                   rest_id: str | None = None) -> dict:
    body = {"phone": phone, "password": "pass123", "name": "U", "role": role}
    if rest_id:
        body["restaurant_id"] = rest_id
    resp = await client.post("/auth/register", json=body)
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def setup_two_restaurants(client, admin, cook1_phone, cook2_phone):
    """Create two restaurants and two cooks. admin is an auth header dict."""
    cat = await client.post(
        "/catalog/categories", json={"name": "Cat", "sort_order": 1}, headers=admin
    )
    item = await client.post(
        "/catalog/items",
        json={"category_id": cat.json()["id"], "name": "Item", "unit": "kg", "variants": []},
        headers=admin,
    )
    rest1 = await client.post(
        "/admin/restaurants",
        json={"name": "Rest1", "address": "A", "contact_phone": "+99670000011"},
        headers=admin,
    )
    rest2 = await client.post(
        "/admin/restaurants",
        json={"name": "Rest2", "address": "B", "contact_phone": "+99670000012"},
        headers=admin,
    )
    rest1_id = rest1.json()["id"]
    rest2_id = rest2.json()["id"]
    cook1 = await register(client, cook1_phone, "cook", rest_id=rest1_id)
    cook2 = await register(client, cook2_phone, "cook", rest_id=rest2_id)
    return cook1, cook2, rest1_id, rest2_id, item.json()["id"]


async def test_cannot_register_as_admin(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "phone": "+99670099901", "password": "pass123", "name": "Hacker", "role": "admin"
    })
    assert resp.status_code == 422


async def test_password_too_short_rejected(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "phone": "+99670099902", "password": "ab", "name": "U", "role": "cook"
    })
    assert resp.status_code == 422


async def test_invalid_phone_format_rejected(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "phone": "not-a-phone", "password": "pass123", "name": "U", "role": "cook"
    })
    assert resp.status_code == 422


async def test_cook_cannot_order_for_other_restaurant(
    client: AsyncClient, admin_token: dict
):
    cook1, cook2, rest1_id, rest2_id, item_id = await setup_two_restaurants(
        client, admin_token, "+99670099904", "+99670099905"
    )
    # cook1 belongs to rest1, tries to create order for rest2
    resp = await client.post(
        "/orders",
        json={"restaurant_id": rest2_id, "items": [{"catalog_item_id": item_id, "quantity": 1.0}]},
        headers=cook1,
    )
    assert resp.status_code == 403


async def test_cook_cannot_read_other_cooks_order(
    client: AsyncClient, admin_token: dict
):
    cook1, cook2, rest1_id, rest2_id, item_id = await setup_two_restaurants(
        client, admin_token, "+99670099907", "+99670099908"
    )
    # cook1 creates an order
    order_resp = await client.post(
        "/orders",
        json={"restaurant_id": rest1_id, "items": [{"catalog_item_id": item_id, "quantity": 1.0}]},
        headers=cook1,
    )
    order_id = order_resp.json()["id"]

    # cook2 tries to GET it
    resp = await client.get(f"/orders/{order_id}", headers=cook2)
    assert resp.status_code == 404


async def test_cook_cannot_create_template_for_other_restaurant(
    client: AsyncClient, admin_token: dict
):
    cook1, cook2, rest1_id, rest2_id, item_id = await setup_two_restaurants(
        client, admin_token, "+99670099910", "+99670099911"
    )
    resp = await client.post(
        "/orders/templates",
        json={
            "name": "Hijack",
            "restaurant_id": rest2_id,
            "items": [{"catalog_item_id": item_id, "quantity": 1.0}],
        },
        headers=cook1,
    )
    assert resp.status_code == 403
