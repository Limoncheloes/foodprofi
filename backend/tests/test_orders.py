import pytest
from httpx import AsyncClient


async def create_cook_with_restaurant(client: AsyncClient, phone: str) -> tuple[str, str]:
    """Returns (access_token, restaurant_id)"""
    # Create restaurant via admin
    admin_resp = await client.post("/auth/register", json={
        "phone": "+996799000001", "password": "adm", "name": "Admin", "role": "admin"
    })
    admin_token = admin_resp.json()["access_token"]

    rest_resp = await client.post("/admin/restaurants", json={
        "name": "Ресторан Тест", "address": "ул. Ленина 1", "contact_phone": "+996700000000"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    rest_id = rest_resp.json()["id"]

    cook_resp = await client.post("/auth/register", json={
        "phone": phone, "password": "pass", "name": "Cook", "role": "cook",
        "restaurant_id": rest_id
    })
    return cook_resp.json()["access_token"], rest_id


async def create_catalog_item(client: AsyncClient, admin_token: str) -> str:
    cat_resp = await client.post("/catalog/categories", json={"name": "Мясо", "sort_order": 1},
                                  headers={"Authorization": f"Bearer {admin_token}"})
    item_resp = await client.post("/catalog/items", json={
        "category_id": cat_resp.json()["id"], "name": "Говядина", "unit": "kg", "variants": []
    }, headers={"Authorization": f"Bearer {admin_token}"})
    return item_resp.json()["id"]


async def test_cook_creates_order(client: AsyncClient):
    cook_token, rest_id = await create_cook_with_restaurant(client, "+996700200001")

    # Need catalog item — get admin token from context (re-register won't work, phone taken)
    admin_resp = await client.post("/auth/login", json={"phone": "+996799000001", "password": "adm"})
    admin_token = admin_resp.json()["access_token"]
    item_id = await create_catalog_item(client, admin_token)

    resp = await client.post("/orders", json={
        "restaurant_id": rest_id,
        "is_urgent": False,
        "items": [{"catalog_item_id": item_id, "quantity": 5.0, "variant": None, "note": None}]
    }, headers={"Authorization": f"Bearer {cook_token}"})

    assert resp.status_code == 201
    order = resp.json()
    assert order["status"] == "submitted"
    assert len(order["items"]) == 1
    assert order["items"][0]["quantity"] == 5.0


async def test_cook_sees_own_orders(client: AsyncClient):
    cook_token, rest_id = await create_cook_with_restaurant(client, "+996700200002")
    resp = await client.get("/orders", headers={"Authorization": f"Bearer {cook_token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_unauthenticated_cannot_create_order(client: AsyncClient):
    resp = await client.post("/orders", json={"restaurant_id": "x", "items": []})
    assert resp.status_code == 403
