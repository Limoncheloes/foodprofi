import uuid
from httpx import AsyncClient


async def register(client: AsyncClient, phone: str, role: str) -> dict:
    resp = await client.post("/auth/register", json={
        "phone": phone, "password": "pass123", "name": "U", "role": role
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def setup_catalog_item(client, admin: dict) -> str:
    """admin is an auth header dict. Returns catalog item id."""
    cat = await client.post(
        "/catalog/categories", json={"name": "K", "sort_order": 1}, headers=admin
    )
    item = await client.post(
        "/catalog/items",
        json={"category_id": cat.json()["id"], "name": "Молоко", "unit": "liters", "variants": []},
        headers=admin,
    )
    return item.json()["id"]


async def test_warehouse_can_list_inventory(client: AsyncClient):
    warehouse = await register(client, "+99670600001", "warehouse")
    resp = await client.get("/warehouse/inventory", headers=warehouse)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_cook_cannot_access_inventory(client: AsyncClient):
    cook = await register(client, "+99670600002", "cook")
    resp = await client.get("/warehouse/inventory", headers=cook)
    assert resp.status_code == 403


async def test_warehouse_can_receive_stock(client: AsyncClient, admin_token: dict):
    warehouse = await register(client, "+99670600004", "warehouse")
    item_id = await setup_catalog_item(client, admin_token)

    resp = await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 10.0},
        headers=warehouse,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["quantity"] == 10.0
    assert data["name"] == "Молоко"
    assert data["unit"] == "liters"


async def test_warehouse_receive_accumulates(client: AsyncClient, admin_token: dict):
    """Two receives add up."""
    warehouse = await register(client, "+99670600006", "warehouse")
    item_id = await setup_catalog_item(client, admin_token)

    await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 10.0},
        headers=warehouse,
    )
    resp = await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 5.0},
        headers=warehouse,
    )
    assert resp.json()["quantity"] == 15.0


async def test_warehouse_can_adjust_stock(client: AsyncClient, admin_token: dict):
    warehouse = await register(client, "+99670600008", "warehouse")
    item_id = await setup_catalog_item(client, admin_token)

    await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 10.0},
        headers=warehouse,
    )

    resp = await client.post(
        "/warehouse/inventory/adjust",
        json={"catalog_item_id": item_id, "quantity": 7.5, "note": "physical count"},
        headers=warehouse,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["previous_quantity"] == 10.0
    assert data["new_quantity"] == 7.5


async def test_receive_negative_quantity_rejected(client: AsyncClient, admin_token: dict):
    warehouse = await register(client, "+99670600010", "warehouse")
    item_id = await setup_catalog_item(client, admin_token)

    resp = await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": -5.0},
        headers=warehouse,
    )
    assert resp.status_code == 422


async def test_receive_nonexistent_item_returns_404(client: AsyncClient):
    warehouse = await register(client, "+99670600011", "warehouse")
    resp = await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": str(uuid.uuid4()), "quantity": 1.0},
        headers=warehouse,
    )
    assert resp.status_code == 404


async def test_inventory_appears_in_list(client: AsyncClient, admin_token: dict):
    warehouse = await register(client, "+99670600013", "warehouse")
    item_id = await setup_catalog_item(client, admin_token)

    await client.post(
        "/warehouse/inventory/receive",
        json={"catalog_item_id": item_id, "quantity": 3.0},
        headers=warehouse,
    )

    resp = await client.get("/warehouse/inventory", headers=warehouse)
    items = resp.json()
    assert any(i["catalog_item_id"] == item_id and i["quantity"] == 3.0 for i in items)


async def test_adjust_nonexistent_item_returns_404(client: AsyncClient):
    warehouse = await register(client, "+99670600014", "warehouse")
    resp = await client.post(
        "/warehouse/inventory/adjust",
        json={"catalog_item_id": str(uuid.uuid4()), "quantity": 5.0},
        headers=warehouse,
    )
    assert resp.status_code == 404


async def test_adjust_without_prior_receive_sets_quantity(
    client: AsyncClient, admin_token: dict
):
    """adjust creates a new Inventory row with previous_quantity=0.0 when none exists."""
    warehouse = await register(client, "+99670600015", "warehouse")
    item_id = await setup_catalog_item(client, admin_token)

    resp = await client.post(
        "/warehouse/inventory/adjust",
        json={"catalog_item_id": item_id, "quantity": 5.0},
        headers=warehouse,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["previous_quantity"] == 0.0
    assert data["new_quantity"] == 5.0
