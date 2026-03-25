import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, phone: str, role: str, rest_id: str | None = None) -> dict:
    body = {"phone": phone, "password": "pass", "name": "U", "role": role}
    if rest_id:
        body["restaurant_id"] = rest_id
    resp = await client.post("/auth/register", json=body)
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def setup(client, admin_phone, cook_phone):
    admin = await register(client, admin_phone, "admin")
    cat = await client.post(
        "/catalog/categories", json={"name": "K", "sort_order": 1}, headers=admin
    )
    item = await client.post(
        "/catalog/items",
        json={"category_id": cat.json()["id"], "name": "I", "unit": "kg", "variants": []},
        headers=admin,
    )
    rest = await client.post(
        "/admin/restaurants",
        json={"name": "R", "address": "A", "contact_phone": "+99670000050"},
        headers=admin,
    )
    rest_id = rest.json()["id"]
    cook = await register(client, cook_phone, "cook", rest_id=rest_id)
    return cook, rest_id, item.json()["id"]


async def test_cook_creates_template(client: AsyncClient):
    cook, rest_id, item_id = await setup(client, "+996700400001", "+996700400002")

    resp = await client.post("/orders/templates", json={
        "name": "Стандартный",
        "restaurant_id": rest_id,
        "items": [{"catalog_item_id": item_id, "quantity": 5.0, "variant": None}],
    }, headers=cook)

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Стандартный"
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 5.0


async def test_cook_lists_only_own_templates(client: AsyncClient):
    cook1, rest_id, item_id = await setup(client, "+996700400003", "+996700400004")
    cook2 = await register(client, "+996700400005", "cook", rest_id=rest_id)

    await client.post("/orders/templates", json={
        "name": "T1", "restaurant_id": rest_id,
        "items": [{"catalog_item_id": item_id, "quantity": 1.0}],
    }, headers=cook1)

    # cook2 sees empty list
    resp = await client.get("/orders/templates", headers=cook2)
    assert resp.status_code == 200
    assert resp.json() == []

    # cook1 sees 1 template
    resp = await client.get("/orders/templates", headers=cook1)
    assert len(resp.json()) == 1


async def test_use_template_creates_submitted_order(client: AsyncClient):
    cook, rest_id, item_id = await setup(client, "+996700400006", "+996700400007")

    tpl = await client.post("/orders/templates", json={
        "name": "T2", "restaurant_id": rest_id,
        "items": [{"catalog_item_id": item_id, "quantity": 2.0}],
    }, headers=cook)
    tpl_id = tpl.json()["id"]

    resp = await client.post(f"/orders/templates/{tpl_id}/use", headers=cook)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "submitted"
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 2.0
    assert data["restaurant_id"] == rest_id


async def test_cannot_use_another_cooks_template(client: AsyncClient):
    cook1, rest_id, item_id = await setup(client, "+996700400008", "+996700400009")
    cook2 = await register(client, "+996700400010", "cook", rest_id=rest_id)

    tpl = await client.post("/orders/templates", json={
        "name": "T3", "restaurant_id": rest_id,
        "items": [{"catalog_item_id": item_id, "quantity": 1.0}],
    }, headers=cook1)
    tpl_id = tpl.json()["id"]

    resp = await client.post(f"/orders/templates/{tpl_id}/use", headers=cook2)
    assert resp.status_code == 404
