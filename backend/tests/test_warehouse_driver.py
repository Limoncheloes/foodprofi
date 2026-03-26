import pytest
import pytest_asyncio
from httpx import AsyncClient


async def register(client: AsyncClient, phone: str, role: str,
                   rest_id: str | None = None) -> dict:
    body = {"phone": phone, "password": "pass123", "name": "U", "role": role}
    if rest_id:
        body["restaurant_id"] = rest_id
    resp = await client.post("/auth/register", json=body)
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def setup(client, admin, cook_phone):
    """Create catalog item, restaurant, cook. admin is already an auth header dict."""
    cat = await client.post(
        "/catalog/categories", json={"name": "C", "sort_order": 1}, headers=admin
    )
    item = await client.post(
        "/catalog/items",
        json={"category_id": cat.json()["id"], "name": "I", "unit": "kg", "variants": []},
        headers=admin,
    )
    rest = await client.post(
        "/admin/restaurants",
        json={"name": "R", "address": "A", "contact_phone": "+99670000030"},
        headers=admin,
    )
    rest_id = rest.json()["id"]
    cook = await register(client, cook_phone, "cook", rest_id=rest_id)
    return cook, rest_id, item.json()["id"]


async def advance_to(client, order_id, target_status, headers):
    """Advance order to target status."""
    resp = await client.patch(
        f"/orders/{order_id}/status", json={"status": target_status}, headers=headers
    )
    assert resp.status_code == 200, f"Failed to advance to {target_status}: {resp.text}"
    return resp


async def test_warehouse_advances_at_warehouse_to_packed(
    client: AsyncClient, admin_token: dict
):
    cook, rest_id, item_id = await setup(client, admin_token, "+99670500002")
    buyer = await register(client, "+99670500003", "buyer")
    warehouse = await register(client, "+99670500004", "warehouse")

    order = await client.post(
        "/orders",
        json={"restaurant_id": rest_id, "items": [{"catalog_item_id": item_id, "quantity": 1.0}]},
        headers=cook,
    )
    order_id = order.json()["id"]

    await advance_to(client, order_id, "in_purchase", buyer)
    await advance_to(client, order_id, "at_warehouse", buyer)

    resp = await client.patch(
        f"/orders/{order_id}/status", json={"status": "packed"}, headers=warehouse
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "packed"


async def test_warehouse_advances_packed_to_in_delivery(
    client: AsyncClient, admin_token: dict
):
    cook, rest_id, item_id = await setup(client, admin_token, "+99670500006")
    buyer = await register(client, "+99670500007", "buyer")
    warehouse = await register(client, "+99670500008", "warehouse")

    order = await client.post(
        "/orders",
        json={"restaurant_id": rest_id, "items": [{"catalog_item_id": item_id, "quantity": 1.0}]},
        headers=cook,
    )
    order_id = order.json()["id"]

    await advance_to(client, order_id, "in_purchase", buyer)
    await advance_to(client, order_id, "at_warehouse", buyer)
    await advance_to(client, order_id, "packed", warehouse)

    resp = await client.patch(
        f"/orders/{order_id}/status", json={"status": "in_delivery"}, headers=warehouse
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_delivery"


async def test_driver_advances_in_delivery_to_delivered(
    client: AsyncClient, admin_token: dict
):
    cook, rest_id, item_id = await setup(client, admin_token, "+99670500010")
    buyer = await register(client, "+99670500011", "buyer")
    warehouse = await register(client, "+99670500012", "warehouse")
    driver = await register(client, "+99670500013", "driver")

    order = await client.post(
        "/orders",
        json={"restaurant_id": rest_id, "items": [{"catalog_item_id": item_id, "quantity": 2.0}]},
        headers=cook,
    )
    order_id = order.json()["id"]

    await advance_to(client, order_id, "in_purchase", buyer)
    await advance_to(client, order_id, "at_warehouse", buyer)
    await advance_to(client, order_id, "packed", warehouse)
    await advance_to(client, order_id, "in_delivery", warehouse)

    resp = await client.patch(
        f"/orders/{order_id}/status", json={"status": "delivered"}, headers=driver
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "delivered"


async def test_warehouse_cannot_skip_to_in_delivery(
    client: AsyncClient, admin_token: dict
):
    """Warehouse cannot go at_warehouse -> in_delivery (must go through packed)."""
    cook, rest_id, item_id = await setup(client, admin_token, "+99670500015")
    buyer = await register(client, "+99670500016", "buyer")
    warehouse = await register(client, "+99670500017", "warehouse")

    order = await client.post(
        "/orders",
        json={"restaurant_id": rest_id, "items": [{"catalog_item_id": item_id, "quantity": 1.0}]},
        headers=cook,
    )
    order_id = order.json()["id"]

    await advance_to(client, order_id, "in_purchase", buyer)
    await advance_to(client, order_id, "at_warehouse", buyer)

    resp = await client.patch(
        f"/orders/{order_id}/status", json={"status": "in_delivery"}, headers=warehouse
    )
    assert resp.status_code == 403


async def test_driver_cannot_mark_packed_as_delivered(
    client: AsyncClient, admin_token: dict
):
    """Driver cannot skip in_delivery."""
    cook, rest_id, item_id = await setup(client, admin_token, "+99670500019")
    buyer = await register(client, "+99670500020", "buyer")
    warehouse = await register(client, "+99670500021", "warehouse")
    driver = await register(client, "+99670500022", "driver")

    order = await client.post(
        "/orders",
        json={"restaurant_id": rest_id, "items": [{"catalog_item_id": item_id, "quantity": 1.0}]},
        headers=cook,
    )
    order_id = order.json()["id"]

    await advance_to(client, order_id, "in_purchase", buyer)
    await advance_to(client, order_id, "at_warehouse", buyer)
    await advance_to(client, order_id, "packed", warehouse)

    resp = await client.patch(
        f"/orders/{order_id}/status", json={"status": "delivered"}, headers=driver
    )
    assert resp.status_code == 403
