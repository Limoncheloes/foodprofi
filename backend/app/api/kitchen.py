import uuid
from datetime import datetime, date, time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user, role_required
from app.database import get_session
from app.models.catalog import CatalogItem
from app.models.order import Order, OrderStatus
from app.models.procurement import ProcurementItem, ProcurementItemStatus
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.schemas.procurement import (
    ProcurementItemRead,
    ProcurementOrderCreate,
    ProcurementOrderRead,
    SubmitOrderResponse,
    WhatsAppUrls,
)
from app.services.routing import route_procurement_order
from app.services.whatsapp import build_order_text, build_whatsapp_urls

router = APIRouter(prefix="/kitchen", tags=["kitchen"])

_COOK_ROLES = (UserRole.cook, UserRole.admin)


def _order_to_read(order: Order, items: list[ProcurementItem]) -> ProcurementOrderRead:
    return ProcurementOrderRead(
        id=order.id,
        restaurant_id=order.restaurant_id,
        restaurant_name=order.restaurant_name,
        user_id=order.user_id,
        user_name=order.user_name,
        status=order.status.value,
        created_at=order.created_at,
        items=[ProcurementItemRead.model_validate(i) for i in items],
    )


@router.post("/orders", response_model=ProcurementOrderRead, status_code=201)
async def create_procurement_order(
    body: ProcurementOrderCreate,
    current_user: User = Depends(role_required(*_COOK_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> ProcurementOrderRead:
    """Create a procurement order draft with items. Does not trigger routing yet."""
    # Verify restaurant exists and belongs to cook
    restaurant = await session.get(Restaurant, body.restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if current_user.role == UserRole.cook and current_user.restaurant_id != body.restaurant_id:
        raise HTTPException(status_code=403, detail="Cannot order for another restaurant")

    order = Order(
        user_id=current_user.id,
        restaurant_id=body.restaurant_id,
        status=OrderStatus.draft,
    )
    session.add(order)
    await session.flush()  # get order.id

    proc_items = []
    for item_data in body.items:
        # Resolve catalog item unit if not raw
        unit = item_data.unit
        if item_data.catalog_item_id:
            cat_item = await session.get(CatalogItem, item_data.catalog_item_id)
            if not cat_item or not cat_item.is_active:
                raise HTTPException(
                    status_code=400,
                    detail=f"Catalog item {item_data.catalog_item_id} not found or inactive",
                )
            if not unit:
                unit = cat_item.unit.value

        proc_item = ProcurementItem(
            order_id=order.id,
            catalog_item_id=item_data.catalog_item_id,
            raw_name=item_data.raw_name,
            quantity_ordered=float(item_data.quantity_ordered),
            unit=unit,
            is_catalog_item=item_data.catalog_item_id is not None,
            status=ProcurementItemStatus.pending_curator,
        )
        session.add(proc_item)
        proc_items.append(proc_item)

    await session.commit()

    # Reload with relationships
    for pi in proc_items:
        await session.refresh(pi)

    # Eagerly load order relationships for response
    result = await session.execute(
        select(Order)
        .where(Order.id == order.id)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
    )
    order = result.scalar_one()

    return _order_to_read(order, proc_items)


@router.post("/orders/{order_id}/submit", response_model=SubmitOrderResponse)
async def submit_procurement_order(
    order_id: uuid.UUID,
    current_user: User = Depends(role_required(*_COOK_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> SubmitOrderResponse:
    """Submit a draft procurement order. Triggers routing, returns WhatsApp URLs."""
    result = await session.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current_user.role == UserRole.cook and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your order")
    if order.status != OrderStatus.draft:
        raise HTTPException(status_code=400, detail="Only draft orders can be submitted")

    # Load procurement items
    items_result = await session.execute(
        select(ProcurementItem)
        .where(ProcurementItem.order_id == order_id)
        .options(selectinload(ProcurementItem.catalog_item))
    )
    items = items_result.scalars().all()
    if not items:
        raise HTTPException(status_code=400, detail="Order has no items")

    # Run routing
    all_assigned = await route_procurement_order(session, order_id)
    order.status = OrderStatus.in_purchase if all_assigned else OrderStatus.routing

    await session.commit()

    # Refresh items after routing updated their statuses
    items_result = await session.execute(
        select(ProcurementItem).where(ProcurementItem.order_id == order_id)
    )
    items = items_result.scalars().all()

    # Build WhatsApp message
    item_dicts = [
        {
            "name": i.display_name,
            "quantity": float(i.quantity_ordered),
            "unit": i.unit,
            "is_catalog_item": i.is_catalog_item,
        }
        for i in items
    ]
    order_date = order.created_at.strftime("%d.%m.%Y")
    text = build_order_text(str(order.id), order_date, order.restaurant_name, item_dicts)
    wa_urls = build_whatsapp_urls(text)

    return SubmitOrderResponse(
        order=_order_to_read(order, items),
        whatsapp=WhatsAppUrls(**wa_urls),
    )


@router.get("/orders", response_model=list[ProcurementOrderRead])
async def list_procurement_orders(
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    restaurant_id: uuid.UUID | None = None,
    current_user: User = Depends(role_required(*_COOK_ROLES, UserRole.manager, UserRole.curator, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> list[ProcurementOrderRead]:
    """List procurement orders with optional filters by status, date range, and restaurant."""
    q = (
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
        .order_by(Order.created_at.desc())
    )
    # Cook and manager see only their restaurant
    if current_user.role in (UserRole.cook, UserRole.manager):
        q = q.where(Order.restaurant_id == current_user.restaurant_id)
    elif restaurant_id:
        q = q.where(Order.restaurant_id == restaurant_id)

    if status:
        try:
            q = q.where(Order.status == OrderStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if date_from:
        q = q.where(Order.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        q = q.where(Order.created_at <= datetime.combine(date_to, time.max))

    orders_result = await session.execute(q)
    orders = orders_result.scalars().all()

    response = []
    for order in orders:
        items_result = await session.execute(
            select(ProcurementItem).where(ProcurementItem.order_id == order.id)
        )
        items = items_result.scalars().all()
        response.append(_order_to_read(order, items))
    return response


@router.get("/orders/{order_id}", response_model=ProcurementOrderRead)
async def get_procurement_order(
    order_id: uuid.UUID,
    current_user: User = Depends(role_required(*_COOK_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> ProcurementOrderRead:
    result = await session.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current_user.role == UserRole.cook and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your order")

    items_result = await session.execute(
        select(ProcurementItem).where(ProcurementItem.order_id == order_id)
    )
    items = items_result.scalars().all()
    return _order_to_read(order, items)
