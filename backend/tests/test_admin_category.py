import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_sets_default_buyer_for_category(client: AsyncClient, admin_token: dict):
    # Create a category via catalog endpoint
    cat_resp = await client.post(
        "/catalog/categories",
        json={"name": "Мясо", "sort_order": 1},
        headers=admin_token,
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    # Register a buyer via admin endpoint
    buyer_resp = await client.post(
        "/admin/users",
        json={"phone": "+99699111001", "password": "pass123", "name": "Buyer", "role": "buyer"},
        headers=admin_token,
    )
    assert buyer_resp.status_code == 201
    buyer_id = buyer_resp.json()["user"]["id"]

    # Set default buyer for category
    resp = await client.patch(
        f"/admin/categories/{cat_id}/buyer",
        json={"default_buyer_id": buyer_id},
        headers=admin_token,
    )
    assert resp.status_code == 200
    assert resp.json()["default_buyer_id"] == buyer_id

    # Clear default buyer
    resp_clear = await client.patch(
        f"/admin/categories/{cat_id}/buyer",
        json={"default_buyer_id": None},
        headers=admin_token,
    )
    assert resp_clear.status_code == 200
    assert resp_clear.json()["default_buyer_id"] is None


@pytest.mark.asyncio
async def test_admin_rejects_invalid_buyer_role(client: AsyncClient, admin_token: dict):
    # Create a category
    cat_resp = await client.post(
        "/catalog/categories",
        json={"name": "Овощи", "sort_order": 2},
        headers=admin_token,
    )
    cat_id = cat_resp.json()["id"]

    # Register a cook (not a buyer)
    cook_resp = await client.post(
        "/admin/users",
        json={"phone": "+99699111002", "password": "pass123", "name": "Cook", "role": "cook"},
        headers=admin_token,
    )
    cook_id = cook_resp.json()["user"]["id"]

    resp = await client.patch(
        f"/admin/categories/{cat_id}/buyer",
        json={"default_buyer_id": cook_id},
        headers=admin_token,
    )
    assert resp.status_code == 400
    assert "Invalid buyer" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_category_buyer_404(client: AsyncClient, admin_token: dict):
    import uuid
    resp = await client.patch(
        f"/admin/categories/{uuid.uuid4()}/buyer",
        json={"default_buyer_id": None},
        headers=admin_token,
    )
    assert resp.status_code == 404
