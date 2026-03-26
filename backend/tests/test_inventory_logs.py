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
