"""Integration tests for buyer procurement endpoints."""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from helpers import TEST_DATABASE_URL, create_admin_headers


async def make_buyer(client: AsyncClient, admin: dict, phone: str, name: str = "Закупщик") -> tuple[dict, str]:
    """Create a buyer user, return (headers, user_id)."""
    resp = await client.post(
        "/admin/users",
        json={"phone": phone, "password": "pass123", "name": name, "role": "buyer"},
        headers=admin,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]["id"]


async def insert_procurement_item(
    order_id: str,
    buyer_id: str | None = None,
    status: str = "assigned",
    qty: float = 5.0,
    unit: str = "кг",
    raw_name: str = "Говядина",
) -> str:
    """Insert a ProcurementItem directly into the DB, return its id."""
    from app.models.procurement import ProcurementItem, ProcurementItemStatus

    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    item_id = uuid.uuid4()
    async with session_factory() as session:
        item = ProcurementItem(
            id=item_id,
            order_id=uuid.UUID(order_id),
            raw_name=raw_name,
            quantity_ordered=qty,
            unit=unit,
            status=ProcurementItemStatus(status),
            is_catalog_item=False,
            buyer_id=uuid.UUID(buyer_id) if buyer_id else None,
        )
        session.add(item)
        await session.commit()
    await engine.dispose()
    return str(item_id)


async def make_order(client: AsyncClient, admin: dict, rest_id: str) -> str:
    """Create an order via admin kitchen endpoint and return its id."""
    # Create a catalog item first
    cat = await client.post(
        "/catalog/categories", json={"name": "Тест", "sort_order": 99}, headers=admin
    )
    cat_id = cat.json()["id"]
    cat_item = await client.post(
        "/catalog/items",
        json={"category_id": cat_id, "name": "Тест товар", "unit": "kg", "variants": []},
        headers=admin,
    )

    # Insert order directly
    from app.models.order import Order, OrderStatus

    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    order_id = uuid.uuid4()
    async with session_factory() as session:
        # Get admin user id
        from sqlalchemy import select
        from app.models.user import User, UserRole
        result = await session.execute(select(User).where(User.role == UserRole.admin).limit(1))
        admin_user = result.scalar_one()
        order = Order(
            id=order_id,
            user_id=admin_user.id,
            restaurant_id=uuid.UUID(rest_id),
            status=OrderStatus.in_purchase,
        )
        session.add(order)
        await session.commit()
    await engine.dispose()
    return str(order_id)


async def setup_env(client: AsyncClient, admin_phone: str, buyer_phone: str):
    """Full setup: admin, buyer, restaurant, order."""
    admin = await create_admin_headers(client, admin_phone)
    buyer, buyer_id = await make_buyer(client, admin, buyer_phone)

    rest = await client.post(
        "/admin/restaurants",
        json={"name": "Кафе", "address": "ул. Ленина 1", "contact_phone": "+99670000099"},
        headers=admin,
    )
    rest_id = rest.json()["id"]
    order_id = await make_order(client, admin, rest_id)
    return admin, buyer, buyer_id, rest_id, order_id


async def test_buyer_can_list_assigned_items(client: AsyncClient):
    admin, buyer, buyer_id, rest_id, order_id = await setup_env(
        client, "+996810100001", "+996810100002"
    )
    item_id = await insert_procurement_item(order_id, buyer_id=buyer_id)

    resp = await client.get("/buyer/items", headers=buyer)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == item_id
    assert data[0]["display_name"] == "Говядина"
    assert data[0]["quantity_ordered"] == 5.0
    assert data[0]["unit"] == "кг"
    assert data[0]["restaurant_name"] == "Кафе"
    assert data[0]["quantity_received"] is None


async def test_buyer_empty_list_when_no_items(client: AsyncClient):
    admin = await create_admin_headers(client, "+996810200001")
    buyer, _ = await make_buyer(client, admin, "+996810200002")

    resp = await client.get("/buyer/items", headers=buyer)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_purchased_items_not_in_list(client: AsyncClient):
    admin, buyer, buyer_id, rest_id, order_id = await setup_env(
        client, "+996810300001", "+996810300002"
    )
    await insert_procurement_item(order_id, buyer_id=buyer_id, status="purchased")

    resp = await client.get("/buyer/items", headers=buyer)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_buyer_cannot_see_other_buyers_items(client: AsyncClient):
    admin, buyer1, buyer1_id, rest_id, order_id = await setup_env(
        client, "+996810400001", "+996810400002"
    )
    buyer2, buyer2_id = await make_buyer(client, admin, "+996810400003", "Закупщик2")
    await insert_procurement_item(order_id, buyer_id=buyer1_id)

    resp = await client.get("/buyer/items", headers=buyer2)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_buyer_mark_purchased_success(client: AsyncClient):
    admin, buyer, buyer_id, rest_id, order_id = await setup_env(
        client, "+996810500001", "+996810500002"
    )
    item_id = await insert_procurement_item(order_id, buyer_id=buyer_id)

    resp = await client.patch(
        f"/buyer/items/{item_id}/purchased",
        json={"quantity_received": 4.5},
        headers=buyer,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["quantity_received"] == 4.5

    # Item gone from assigned list
    list_resp = await client.get("/buyer/items", headers=buyer)
    assert list_resp.json() == []


async def test_buyer_mark_purchased_invalid_quantity(client: AsyncClient):
    admin, buyer, buyer_id, rest_id, order_id = await setup_env(
        client, "+996810600001", "+996810600002"
    )
    item_id = await insert_procurement_item(order_id, buyer_id=buyer_id)

    resp = await client.patch(
        f"/buyer/items/{item_id}/purchased",
        json={"quantity_received": 0},
        headers=buyer,
    )
    assert resp.status_code == 422


async def test_buyer_cannot_mark_others_item(client: AsyncClient):
    admin, buyer1, buyer1_id, rest_id, order_id = await setup_env(
        client, "+996810700001", "+996810700002"
    )
    buyer2, _ = await make_buyer(client, admin, "+996810700003", "Закупщик2")
    item_id = await insert_procurement_item(order_id, buyer_id=buyer1_id)

    resp = await client.patch(
        f"/buyer/items/{item_id}/purchased",
        json={"quantity_received": 3.0},
        headers=buyer2,
    )
    assert resp.status_code == 403


async def test_buyer_mark_purchased_not_found(client: AsyncClient):
    admin = await create_admin_headers(client, "+996810800001")
    buyer, _ = await make_buyer(client, admin, "+996810800002")

    resp = await client.patch(
        f"/buyer/items/{uuid.uuid4()}/purchased",
        json={"quantity_received": 1.0},
        headers=buyer,
    )
    assert resp.status_code == 404


async def test_cook_cannot_access_buyer_endpoints(client: AsyncClient):
    cook_resp = await client.post(
        "/auth/register",
        json={"phone": "+996810900001", "password": "pass123", "name": "Повар"},
    )
    cook = {"Authorization": f"Bearer {cook_resp.json()['access_token']}"}

    resp = await client.get("/buyer/items", headers=cook)
    assert resp.status_code == 403
