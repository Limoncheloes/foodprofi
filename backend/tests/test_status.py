import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, phone: str, role: str, name: str = "U",
                   rest_id: str | None = None) -> dict:
    body = {"phone": phone, "password": "pass", "name": name, "role": role}
    if rest_id:
        body["restaurant_id"] = rest_id
    resp = await client.post("/auth/register", json=body)
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def create_order(client, cook_headers, rest_id, item_id):
    resp = await client.post("/orders", json={
        "restaurant_id": rest_id,
        "items": [{"catalog_item_id": item_id, "quantity": 1.0}],
    }, headers=cook_headers)
    return resp.json()["id"]


async def setup_all(client, admin_phone, cook_phone, buyer_phone=None):
    admin = await register(client, admin_phone, "admin")
    cat = await client.post(
        "/catalog/categories", json={"name": "Cat", "sort_order": 1}, headers=admin
    )
    item = await client.post(
        "/catalog/items",
        json={"category_id": cat.json()["id"], "name": "Item", "unit": "kg", "variants": []},
        headers=admin,
    )
    rest = await client.post(
        "/admin/restaurants",
        json={"name": "R", "address": "A", "contact_phone": "+99670000099"},
        headers=admin,
    )
    rest_id = rest.json()["id"]
    cook = await register(client, cook_phone, "cook", rest_id=rest_id)
    buyer = await register(client, buyer_phone, "buyer") if buyer_phone else None
    return admin, cook, buyer, rest_id, item.json()["id"]


async def test_buyer_advances_submitted_to_in_purchase(client: AsyncClient):
    admin, cook, buyer, rest_id, item_id = await setup_all(
        client, "+996700300001", "+996700300002", "+996700300003"
    )
    order_id = await create_order(client, cook, rest_id, item_id)

    resp = await client.patch(
        f"/orders/{order_id}/status",
        json={"status": "in_purchase"},
        headers=buyer,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_purchase"


async def test_buyer_advances_in_purchase_to_at_warehouse(client: AsyncClient):
    admin, cook, buyer, rest_id, item_id = await setup_all(
        client, "+996700300004", "+996700300005", "+996700300006"
    )
    order_id = await create_order(client, cook, rest_id, item_id)

    # submitted → in_purchase
    await client.patch(
        f"/orders/{order_id}/status", json={"status": "in_purchase"}, headers=buyer
    )
    # in_purchase → at_warehouse
    resp = await client.patch(
        f"/orders/{order_id}/status", json={"status": "at_warehouse"}, headers=buyer
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "at_warehouse"


async def test_cook_cannot_advance_status(client: AsyncClient):
    admin, cook, buyer, rest_id, item_id = await setup_all(
        client, "+996700300007", "+996700300008", "+996700300009"
    )
    order_id = await create_order(client, cook, rest_id, item_id)

    resp = await client.patch(
        f"/orders/{order_id}/status",
        json={"status": "in_purchase"},
        headers=cook,
    )
    assert resp.status_code == 403


async def test_invalid_transition_rejected(client: AsyncClient):
    """Buyer cannot skip submitted → directly to at_warehouse."""
    admin, cook, buyer, rest_id, item_id = await setup_all(
        client, "+996700300010", "+996700300011", "+996700300012"
    )
    order_id = await create_order(client, cook, rest_id, item_id)

    resp = await client.patch(
        f"/orders/{order_id}/status",
        json={"status": "at_warehouse"},
        headers=buyer,
    )
    assert resp.status_code == 403


async def test_admin_can_cancel_any_order(client: AsyncClient):
    admin, cook, _, rest_id, item_id = await setup_all(
        client, "+996700300013", "+996700300014"
    )
    order_id = await create_order(client, cook, rest_id, item_id)

    resp = await client.patch(
        f"/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers=admin,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
