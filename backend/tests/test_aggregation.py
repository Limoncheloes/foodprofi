from datetime import date
import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, phone: str, role: str, name: str = "U",
                   rest_id: str | None = None) -> dict:
    body = {"phone": phone, "password": "pass", "name": name, "role": role}
    if rest_id:
        body["restaurant_id"] = rest_id
    resp = await client.post("/auth/register", json=body)
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def setup_catalog(client, admin):
    """Create one category and one item, return (cat_id, item_id)."""
    cat = await client.post(
        "/catalog/categories", json={"name": "Мясо", "sort_order": 1}, headers=admin
    )
    item = await client.post(
        "/catalog/items",
        json={"category_id": cat.json()["id"], "name": "Говядина", "unit": "kg", "variants": []},
        headers=admin,
    )
    return cat.json()["id"], item.json()["id"]


async def test_aggregation_empty(client: AsyncClient):
    buyer = await register(client, "+996700200001", "buyer")
    resp = await client.get(
        "/aggregation/summary",
        params={"target_date": str(date.today())},
        headers=buyer,
    )
    assert resp.status_code == 200
    assert resp.json()["categories"] == []


async def test_aggregation_requires_buyer_role(client: AsyncClient):
    cook = await register(client, "+996700200002", "cook")
    resp = await client.get("/aggregation/summary", headers=cook)
    assert resp.status_code == 403


async def test_aggregation_groups_by_category(client: AsyncClient):
    admin = await register(client, "+996700200003", "admin")
    buyer = await register(client, "+996700200004", "buyer")
    _, item_id = await setup_catalog(client, admin)

    rest = await client.post(
        "/admin/restaurants",
        json={"name": "R1", "address": "A", "contact_phone": "+99670000001"},
        headers=admin,
    )
    rest_id = rest.json()["id"]
    cook = await register(client, "+996700200005", "cook", rest_id=rest_id)

    await client.post(
        "/orders",
        json={"restaurant_id": rest_id, "items": [{"catalog_item_id": item_id, "quantity": 5.0}]},
        headers=cook,
    )

    resp = await client.get(
        "/aggregation/summary",
        params={"target_date": str(date.today())},
        headers=buyer,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["categories"]) == 1
    assert data["categories"][0]["category_name"] == "Мясо"
    item = data["categories"][0]["items"][0]
    assert item["total_needed"] == 5.0
    assert item["to_buy"] == 5.0
    assert item["in_stock"] == 0.0
    assert len(item["restaurants"]) == 1


async def test_aggregation_subtracts_inventory(client: AsyncClient):
    """If inventory has 2kg and order needs 5kg, to_buy should be 3kg."""
    admin = await register(client, "+996700200006", "admin")
    buyer = await register(client, "+996700200007", "buyer")
    _, item_id = await setup_catalog(client, admin)

    rest = await client.post(
        "/admin/restaurants",
        json={"name": "R2", "address": "A", "contact_phone": "+99670000002"},
        headers=admin,
    )
    rest_id = rest.json()["id"]
    cook = await register(client, "+996700200008", "cook", rest_id=rest_id)

    # Simulate existing stock (2kg)
    await client.post(
        "/aggregation/mark-purchased",
        json={
            "date": str(date.today()),
            "purchases": [{"catalog_item_id": item_id, "quantity_bought": 2.0}],
        },
        headers=buyer,
    )

    # Cook orders 5kg
    await client.post(
        "/orders",
        json={"restaurant_id": rest_id, "items": [{"catalog_item_id": item_id, "quantity": 5.0}]},
        headers=cook,
    )

    resp = await client.get(
        "/aggregation/summary",
        params={"target_date": str(date.today())},
        headers=buyer,
    )
    item = resp.json()["categories"][0]["items"][0]
    assert item["total_needed"] == 5.0
    assert item["in_stock"] == 2.0
    assert item["to_buy"] == 3.0


async def test_mark_purchased_advances_order_status(client: AsyncClient):
    admin = await register(client, "+996700200009", "admin")
    buyer = await register(client, "+996700200010", "buyer")
    _, item_id = await setup_catalog(client, admin)

    rest = await client.post(
        "/admin/restaurants",
        json={"name": "R3", "address": "A", "contact_phone": "+99670000003"},
        headers=admin,
    )
    rest_id = rest.json()["id"]
    cook = await register(client, "+996700200011", "cook", rest_id=rest_id)

    order_resp = await client.post(
        "/orders",
        json={"restaurant_id": rest_id, "items": [{"catalog_item_id": item_id, "quantity": 3.0}]},
        headers=cook,
    )
    order_id = order_resp.json()["id"]
    assert order_resp.json()["status"] == "submitted"

    await client.post(
        "/aggregation/mark-purchased",
        json={
            "date": str(date.today()),
            "purchases": [{"catalog_item_id": item_id, "quantity_bought": 3.0}],
        },
        headers=buyer,
    )

    # Check order status advanced
    order = await client.get(f"/orders/{order_id}", headers=cook)
    assert order.json()["status"] == "in_purchase"
