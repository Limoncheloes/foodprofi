from httpx import AsyncClient
from sqlalchemy import select


async def register(client: AsyncClient, phone: str, role: str, rest_id: str | None = None) -> dict:
    body = {"phone": phone, "password": "pass123", "name": "U", "role": role}
    if rest_id:
        body["restaurant_id"] = rest_id
    resp = await client.post("/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def setup(client: AsyncClient, admin: dict, base_phone: str, order_qty: float = 3.0):
    """Returns cook, buyer, warehouse, driver, order_id, item_id."""
    cat = await client.post("/catalog/categories", json={"name": "C", "sort_order": 1}, headers=admin)
    item = await client.post(
        "/catalog/items",
        json={"category_id": cat.json()["id"], "name": "Milk", "unit": "liters", "variants": []},
        headers=admin,
    )
    rest = await client.post(
        "/admin/restaurants",
        json={"name": "R", "address": "A", "contact_phone": "+99671100001"},
        headers=admin,
    )
    rest_id = rest.json()["id"]
    item_id = item.json()["id"]

    cook = await register(client, base_phone + "0", "cook", rest_id)
    buyer = await register(client, base_phone + "1", "buyer")
    warehouse = await register(client, base_phone + "2", "warehouse")
    driver = await register(client, base_phone + "3", "driver")

    order = await client.post(
        "/orders",
        json={"restaurant_id": rest_id, "items": [{"catalog_item_id": item_id, "quantity": order_qty}]},
        headers=cook,
    )
    assert order.status_code == 201, order.text
    return cook, buyer, warehouse, driver, order.json()["id"], item_id


async def advance_to_delivered(client, order_id, buyer, warehouse, driver):
    for status, headers in [
        ("in_purchase", buyer),
        ("at_warehouse", buyer),
        ("packed", warehouse),
        ("in_delivery", warehouse),
        ("delivered", driver),
    ]:
        r = await client.patch(f"/orders/{order_id}/status", json={"status": status}, headers=headers)
        assert r.status_code == 200, f"Failed to advance to {status}: {r.text}"
    return r


async def test_delivery_deducts_inventory(client: AsyncClient, admin_token: dict):
    """Delivering an order reduces inventory by the ordered quantities."""
    _, buyer, warehouse, driver, order_id, item_id = await setup(
        client, admin_token, "+9967110000", order_qty=3.0
    )

    # Receive 10 units first
    await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 10.0},
        headers=warehouse,
    )

    await advance_to_delivered(client, order_id, buyer, warehouse, driver)

    inv_resp = await client.get("/warehouse/inventory", headers=warehouse)
    assert inv_resp.status_code == 200
    items = inv_resp.json()
    entry = next((i for i in items if i["catalog_item_id"] == item_id), None)
    assert entry is not None
    assert entry["quantity"] == 7.0  # 10 - 3


async def test_delivery_allows_negative_stock(client: AsyncClient, admin_token: dict):
    """Delivery can push inventory below zero — no server error."""
    _, buyer, warehouse, driver, order_id, item_id = await setup(
        client, admin_token, "+9967110004", order_qty=5.0
    )

    # Receive only 2 units (order is 5)
    await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 2.0},
        headers=warehouse,
    )

    resp = await advance_to_delivered(client, order_id, buyer, warehouse, driver)
    assert resp.status_code == 200

    inv_resp = await client.get("/warehouse/inventory", headers=warehouse)
    entry = next(i for i in inv_resp.json() if i["catalog_item_id"] == item_id)
    assert entry["quantity"] == -3.0  # 2 - 5


async def test_delivery_without_prior_receive_creates_negative_inventory(
    client: AsyncClient, admin_token: dict
):
    """If no stock was received, delivering an order creates a negative inventory entry."""
    _, buyer, warehouse, driver, order_id, item_id = await setup(
        client, admin_token, "+9967110008", order_qty=4.0
    )

    resp = await advance_to_delivered(client, order_id, buyer, warehouse, driver)
    assert resp.status_code == 200

    inv_resp = await client.get("/warehouse/inventory", headers=warehouse)
    entry = next((i for i in inv_resp.json() if i["catalog_item_id"] == item_id), None)
    assert entry is not None
    assert entry["quantity"] == -4.0


async def test_delivery_creates_consumed_log_in_db(client: AsyncClient, admin_token: dict):
    """Delivering an order writes InventoryLog entries with reason=consumed."""
    from conftest import TestSession
    from app.models.inventory import InventoryLog, InventoryReason

    _, buyer, warehouse, driver, order_id, item_id = await setup(
        client, admin_token, "+9967110012", order_qty=2.0
    )
    await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 5.0},
        headers=warehouse,
    )
    await advance_to_delivered(client, order_id, buyer, warehouse, driver)

    async with TestSession() as session:
        result = await session.execute(
            select(InventoryLog).where(
                InventoryLog.catalog_item_id == item_id,
                InventoryLog.reason == InventoryReason.consumed,
            )
        )
        logs = result.scalars().all()

    assert len(logs) == 1
    assert logs[0].delta == -2.0
