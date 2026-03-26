from httpx import AsyncClient


async def register(client: AsyncClient, phone: str, role: str) -> dict:
    resp = await client.post("/auth/register", json={
        "phone": phone, "password": "pass123", "name": "U", "role": role
    })
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def setup_item(client: AsyncClient, admin: dict) -> str:
    cat = await client.post("/catalog/categories", json={"name": "C", "sort_order": 1}, headers=admin)
    item = await client.post(
        "/catalog/items",
        json={"category_id": cat.json()["id"], "name": "Sugar", "unit": "kg", "variants": []},
        headers=admin,
    )
    return item.json()["id"]


async def test_logs_empty_on_fresh_db(client: AsyncClient):
    warehouse = await register(client, "+9967120001", "warehouse")
    resp = await client.get("/warehouse/inventory/logs", headers=warehouse)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_receive_creates_log_entry(client: AsyncClient, admin_token: dict):
    warehouse = await register(client, "+9967120003", "warehouse")
    item_id = await setup_item(client, admin_token)

    await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 8.0, "note": "fresh batch"},
        headers=warehouse,
    )

    resp = await client.get("/warehouse/inventory/logs", headers=warehouse)
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) == 1
    log = logs[0]
    assert log["catalog_item_id"] == item_id
    assert log["item_name"] == "Sugar"
    assert log["delta"] == 8.0
    assert log["reason"] == "received"
    assert log["note"] == "fresh batch"
    assert "created_at" in log
    assert "user_name" in log


async def test_adjust_creates_log_entry(client: AsyncClient, admin_token: dict):
    warehouse = await register(client, "+9967120005", "warehouse")
    item_id = await setup_item(client, admin_token)

    await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 10.0},
        headers=warehouse,
    )
    await client.post(
        "/warehouse/inventory/adjust",
        json={"catalog_item_id": item_id, "quantity": 6.0, "note": "count"},
        headers=warehouse,
    )

    resp = await client.get("/warehouse/inventory/logs", headers=warehouse)
    logs = resp.json()
    assert len(logs) == 2
    reasons = {l["reason"] for l in logs}
    assert "received" in reasons
    assert "adjusted" in reasons


async def test_logs_ordered_newest_first(client: AsyncClient, admin_token: dict):
    warehouse = await register(client, "+9967120007", "warehouse")
    item_id = await setup_item(client, admin_token)

    await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 5.0},
        headers=warehouse,
    )
    await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 3.0},
        headers=warehouse,
    )

    resp = await client.get("/warehouse/inventory/logs", headers=warehouse)
    logs = resp.json()
    assert logs[0]["delta"] == 3.0  # most recent first
    assert logs[1]["delta"] == 5.0


async def test_cook_cannot_access_logs(client: AsyncClient):
    cook = await register(client, "+9967120009", "cook")
    resp = await client.get("/warehouse/inventory/logs", headers=cook)
    assert resp.status_code == 403


async def test_consumed_log_visible_in_api(client: AsyncClient, admin_token: dict):
    """Delivering an order creates a consumed log entry visible via GET /warehouse/inventory/logs."""
    cat = await client.post("/catalog/categories", json={"name": "C", "sort_order": 1}, headers=admin_token)
    item = await client.post(
        "/catalog/items",
        json={"category_id": cat.json()["id"], "name": "Flour", "unit": "kg", "variants": []},
        headers=admin_token,
    )
    rest = await client.post(
        "/admin/restaurants",
        json={"name": "R", "address": "A", "contact_phone": "+99671200099"},
        headers=admin_token,
    )
    rest_id = rest.json()["id"]
    item_id = item.json()["id"]

    cook_resp = await client.post("/auth/register", json={
        "phone": "+9967120011", "password": "pass123", "name": "Cook", "role": "cook",
        "restaurant_id": rest_id,
    })
    cook = {"Authorization": f"Bearer {cook_resp.json()['access_token']}"}
    buyer = await register(client, "+9967120012", "buyer")
    warehouse = await register(client, "+9967120013", "warehouse")
    driver = await register(client, "+9967120014", "driver")

    await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 10.0},
        headers=warehouse,
    )

    order = await client.post(
        "/orders",
        json={"restaurant_id": rest_id, "items": [{"catalog_item_id": item_id, "quantity": 3.0}]},
        headers=cook,
    )
    order_id = order.json()["id"]

    for status, headers in [
        ("in_purchase", buyer), ("at_warehouse", buyer),
        ("packed", warehouse), ("in_delivery", warehouse), ("delivered", driver),
    ]:
        await client.patch(f"/orders/{order_id}/status", json={"status": status}, headers=headers)

    resp = await client.get("/warehouse/inventory/logs", headers=warehouse)
    logs = resp.json()
    reasons = {l["reason"] for l in logs}
    assert "consumed" in reasons
    consumed = next(l for l in logs if l["reason"] == "consumed")
    assert consumed["delta"] == -3.0
    assert consumed["catalog_item_id"] == item_id
