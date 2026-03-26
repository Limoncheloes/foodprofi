import pytest
from httpx import AsyncClient

from helpers import create_admin_headers


async def test_list_categories_empty(client: AsyncClient):
    resp = await client.get("/catalog/categories")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_admin_creates_category_and_item(client: AsyncClient):
    headers = await create_admin_headers(client, "+996700100001")

    # Create category
    resp = await client.post("/catalog/categories", json={"name": "Мясо", "sort_order": 1}, headers=headers)
    assert resp.status_code == 201
    cat_id = resp.json()["id"]

    # Create item
    resp = await client.post("/catalog/items", json={
        "category_id": cat_id,
        "name": "Говядина",
        "unit": "kg",
        "variants": ["с костью", "без кости"],
    }, headers=headers)
    assert resp.status_code == 201
    item = resp.json()
    assert item["name"] == "Говядина"
    assert len(item["variants"]) == 2


async def test_list_items_by_category(client: AsyncClient):
    headers = await create_admin_headers(client, "+996700100003")

    resp = await client.post("/catalog/categories", json={"name": "Овощи", "sort_order": 2}, headers=headers)
    cat_id = resp.json()["id"]
    await client.post("/catalog/items", json={"category_id": cat_id, "name": "Морковь", "unit": "kg", "variants": []}, headers=headers)

    resp = await client.get(f"/catalog/items?category_id={cat_id}")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_cook_cannot_create_item(client: AsyncClient):
    cook_resp = await client.post("/auth/register", json={
        "phone": "+996700100002", "password": "pass123", "name": "Cook", "role": "cook"
    })
    token = cook_resp.json()["access_token"]
    resp = await client.post("/catalog/items", json={
        "category_id": "00000000-0000-0000-0000-000000000000",
        "name": "X", "unit": "kg", "variants": []
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
