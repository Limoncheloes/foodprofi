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
