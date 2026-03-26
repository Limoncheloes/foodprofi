from httpx import AsyncClient

from helpers import create_admin_headers


async def make_restaurant_and_manager(client: AsyncClient, phone_suffix: str) -> tuple[dict, dict, str]:
    """Returns (admin_headers, manager_headers, restaurant_id)."""
    admin = await create_admin_headers(client, f"+9960000{phone_suffix}0")

    rest = await client.post("/admin/restaurants", json={
        "name": "Кафе Тест", "address": "ул. Тест 1", "contact_phone": "+99670000000",
    }, headers=admin)
    rest_id = rest.json()["id"]

    mgr_resp = await client.post("/admin/users", json={
        "phone": f"+9960000{phone_suffix}1",
        "password": "pass123",
        "name": "Менеджер",
        "role": "manager",
        "restaurant_id": rest_id,
    }, headers=admin)
    assert mgr_resp.status_code == 201, mgr_resp.text
    mgr_token = mgr_resp.json()["access_token"]
    manager = {"Authorization": f"Bearer {mgr_token}"}
    return admin, manager, rest_id


async def test_admin_creates_manager(client: AsyncClient):
    admin = await create_admin_headers(client, "+996000100010")
    rest = await client.post("/admin/restaurants", json={
        "name": "R", "address": "A", "contact_phone": "+99600000000",
    }, headers=admin)
    rest_id = rest.json()["id"]

    resp = await client.post("/admin/users", json={
        "phone": "+996000100011",
        "password": "pass123",
        "name": "Менеджер 1",
        "role": "manager",
        "restaurant_id": rest_id,
    }, headers=admin)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["role"] == "manager"
    assert data["user"]["restaurant_id"] == rest_id


async def test_non_admin_cannot_create_user(client: AsyncClient):
    cook_resp = await client.post("/auth/register", json={
        "phone": "+996000100020", "password": "pass123", "name": "Cook", "role": "cook",
    })
    cook = {"Authorization": f"Bearer {cook_resp.json()['access_token']}"}
    resp = await client.post("/admin/users", json={
        "phone": "+996000100021", "password": "pass123", "name": "X", "role": "cook",
    }, headers=cook)
    assert resp.status_code == 403


async def test_manager_can_add_cook(client: AsyncClient):
    _, manager, rest_id = await make_restaurant_and_manager(client, "200")

    resp = await client.post("/manager/staff", json={
        "phone": "+996000200010",
        "password": "pass123",
        "name": "Повар Азиз",
        "role": "cook",
    }, headers=manager)
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "cook"
    assert data["restaurant_id"] == rest_id


async def test_manager_cannot_add_buyer_role(client: AsyncClient):
    _, manager, _ = await make_restaurant_and_manager(client, "210")

    resp = await client.post("/manager/staff", json={
        "phone": "+996000210010",
        "password": "pass123",
        "name": "X",
        "role": "buyer",
    }, headers=manager)
    assert resp.status_code == 422  # validation error — buyer not in allowed roles


async def test_manager_lists_staff(client: AsyncClient):
    _, manager, _ = await make_restaurant_and_manager(client, "220")

    await client.post("/manager/staff", json={
        "phone": "+996000220010", "password": "pass123", "name": "Cook1", "role": "cook",
    }, headers=manager)

    resp = await client.get("/manager/staff", headers=manager)
    assert resp.status_code == 200
    staff = resp.json()
    roles = {s["role"] for s in staff}
    assert "manager" in roles
    assert "cook" in roles


async def test_manager_views_restaurant_orders(client: AsyncClient):
    admin, manager, rest_id = await make_restaurant_and_manager(client, "230")

    cook_resp = await client.post("/manager/staff", json={
        "phone": "+996000230010", "password": "pass123", "name": "Cook", "role": "cook",
    }, headers=manager)
    cook_token = cook_resp.json()["access_token"]
    cook_headers = {"Authorization": f"Bearer {cook_token}"}

    cat = await client.post("/catalog/categories", json={"name": "C", "sort_order": 1}, headers=admin)
    item = await client.post("/catalog/items", json={
        "category_id": cat.json()["id"], "name": "Flour", "unit": "kg", "variants": [],
    }, headers=admin)
    item_id = item.json()["id"]

    await client.post("/orders", json={
        "restaurant_id": rest_id,
        "items": [{"catalog_item_id": item_id, "quantity": 2.0}],
    }, headers=cook_headers)

    resp = await client.get("/manager/orders", headers=manager)
    assert resp.status_code == 200
    orders = resp.json()
    assert len(orders) >= 1
    assert "user_name" in orders[0]


async def test_manager_reads_settings(client: AsyncClient):
    _, manager, _ = await make_restaurant_and_manager(client, "240")

    resp = await client.get("/manager/settings", headers=manager)
    assert resp.status_code == 200
    assert resp.json()["requires_approval"] is False


async def test_manager_updates_settings(client: AsyncClient):
    _, manager, _ = await make_restaurant_and_manager(client, "250")

    resp = await client.patch("/manager/settings", json={"requires_approval": True}, headers=manager)
    assert resp.status_code == 200
    assert resp.json()["requires_approval"] is True

    resp2 = await client.get("/manager/settings", headers=manager)
    assert resp2.json()["requires_approval"] is True


async def test_cook_cannot_access_manager_endpoints(client: AsyncClient):
    cook_resp = await client.post("/auth/register", json={
        "phone": "+996000260010", "password": "pass123", "name": "Cook", "role": "cook",
    })
    cook = {"Authorization": f"Bearer {cook_resp.json()['access_token']}"}
    resp = await client.get("/manager/staff", headers=cook)
    assert resp.status_code == 403


async def _setup_approval_scenario(client: AsyncClient, phone_suffix: str):
    """Returns (admin_headers, manager_headers, cook_headers, rest_id, item_id)."""
    admin, manager, rest_id = await make_restaurant_and_manager(client, phone_suffix)

    # Enable approval
    await client.patch("/manager/settings", json={"requires_approval": True}, headers=manager)

    # Add cook
    cook_resp = await client.post("/manager/staff", json={
        "phone": f"+99600{phone_suffix}0010",
        "password": "pass123",
        "name": "Cook",
        "role": "cook",
    }, headers=manager)
    cook = {"Authorization": f"Bearer {cook_resp.json()['access_token']}"}

    # Create catalog item
    cat = await client.post("/catalog/categories", json={"name": "C", "sort_order": 1}, headers=admin)
    item = await client.post("/catalog/items", json={
        "category_id": cat.json()["id"], "name": "Rice", "unit": "kg", "variants": [],
    }, headers=admin)

    return admin, manager, cook, rest_id, item.json()["id"]


async def test_order_created_as_pending_when_approval_required(client: AsyncClient):
    _, _, cook, rest_id, item_id = await _setup_approval_scenario(client, "300")

    resp = await client.post("/orders", json={
        "restaurant_id": rest_id,
        "items": [{"catalog_item_id": item_id, "quantity": 1.0}],
    }, headers=cook)
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending_approval"


async def test_order_created_as_submitted_when_no_approval_required(client: AsyncClient):
    _, manager, rest_id = await make_restaurant_and_manager(client, "310")
    # requires_approval defaults to False

    cook_resp = await client.post("/manager/staff", json={
        "phone": "+99600031010", "password": "pass123", "name": "Cook", "role": "cook",
    }, headers=manager)
    cook = {"Authorization": f"Bearer {cook_resp.json()['access_token']}"}

    admin_h = await create_admin_headers(client, "+9960031099")
    cat = await client.post("/catalog/categories", json={"name": "C", "sort_order": 1}, headers=admin_h)
    item = await client.post("/catalog/items", json={
        "category_id": cat.json()["id"], "name": "Salt", "unit": "kg", "variants": [],
    }, headers=admin_h)

    resp = await client.post("/orders", json={
        "restaurant_id": rest_id,
        "items": [{"catalog_item_id": item.json()["id"], "quantity": 1.0}],
    }, headers=cook)
    assert resp.status_code == 201
    assert resp.json()["status"] == "submitted"


async def test_manager_approves_order(client: AsyncClient):
    _, manager, cook, rest_id, item_id = await _setup_approval_scenario(client, "320")

    order_resp = await client.post("/orders", json={
        "restaurant_id": rest_id,
        "items": [{"catalog_item_id": item_id, "quantity": 1.0}],
    }, headers=cook)
    order_id = order_resp.json()["id"]
    assert order_resp.json()["status"] == "pending_approval"

    resp = await client.patch(f"/orders/{order_id}/status",
                              json={"status": "submitted"}, headers=manager)
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"


async def test_manager_rejects_order(client: AsyncClient):
    _, manager, cook, rest_id, item_id = await _setup_approval_scenario(client, "330")

    order_resp = await client.post("/orders", json={
        "restaurant_id": rest_id,
        "items": [{"catalog_item_id": item_id, "quantity": 1.0}],
    }, headers=cook)
    order_id = order_resp.json()["id"]

    resp = await client.patch(f"/orders/{order_id}/status",
                              json={"status": "cancelled"}, headers=manager)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_manager_cannot_approve_other_restaurants_order(client: AsyncClient):
    _, manager_a, cook_a, rest_a, item_id = await _setup_approval_scenario(client, "340")
    _, manager_b, _ = await make_restaurant_and_manager(client, "341")

    order_resp = await client.post("/orders", json={
        "restaurant_id": rest_a,
        "items": [{"catalog_item_id": item_id, "quantity": 1.0}],
    }, headers=cook_a)
    order_id = order_resp.json()["id"]

    resp = await client.patch(f"/orders/{order_id}/status",
                              json={"status": "submitted"}, headers=manager_b)
    assert resp.status_code == 403


async def test_cook_cannot_approve(client: AsyncClient):
    _, manager, cook, rest_id, item_id = await _setup_approval_scenario(client, "350")

    order_resp = await client.post("/orders", json={
        "restaurant_id": rest_id,
        "items": [{"catalog_item_id": item_id, "quantity": 1.0}],
    }, headers=cook)
    order_id = order_resp.json()["id"]

    resp = await client.patch(f"/orders/{order_id}/status",
                              json={"status": "submitted"}, headers=cook)
    assert resp.status_code == 403


async def test_manager_cannot_approve_already_submitted_order(client: AsyncClient):
    _, manager, cook, rest_id, item_id = await _setup_approval_scenario(client, "360")

    order_resp = await client.post("/orders", json={
        "restaurant_id": rest_id,
        "items": [{"catalog_item_id": item_id, "quantity": 1.0}],
    }, headers=cook)
    order_id = order_resp.json()["id"]

    # First approval succeeds
    await client.patch(f"/orders/{order_id}/status", json={"status": "submitted"}, headers=manager)

    # Second attempt on already-submitted order must be rejected
    resp = await client.patch(f"/orders/{order_id}/status", json={"status": "submitted"}, headers=manager)
    assert resp.status_code == 403
