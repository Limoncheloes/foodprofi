import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import role_required
from app.database import get_session
from app.models.order import Order
from app.models.procurement import ProcurementItem, ProcurementItemStatus
from app.models.user import User, UserRole
from app.schemas.buyer import BuyerItemRead, MarkPurchasedRequest

router = APIRouter(prefix="/buyer", tags=["buyer"])

_BUYER_ROLES = (UserRole.buyer, UserRole.admin)


@router.get("/items", response_model=list[BuyerItemRead])
async def list_buyer_items(
    current_user: User = Depends(role_required(*_BUYER_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> list[BuyerItemRead]:
    result = await session.execute(
        select(ProcurementItem)
        .where(
            ProcurementItem.buyer_id == current_user.id,
            ProcurementItem.status == ProcurementItemStatus.assigned,
        )
        .options(selectinload(ProcurementItem.catalog_item))
        .order_by(ProcurementItem.created_at.asc())
    )
    items = result.scalars().all()

    if not items:
        return []

    order_ids = list({item.order_id for item in items})
    orders_result = await session.execute(
        select(Order)
        .where(Order.id.in_(order_ids))
        .options(selectinload(Order.restaurant))
    )
    order_map = {o.id: o for o in orders_result.scalars().all()}

    return [
        BuyerItemRead(
            id=item.id,
            order_id=item.order_id,
            display_name=item.display_name,
            quantity_ordered=float(item.quantity_ordered),
            quantity_received=float(item.quantity_received) if item.quantity_received is not None else None,
            unit=item.unit,
            restaurant_name=order_map[item.order_id].restaurant_name if item.order_id in order_map else "",
            order_date=order_map[item.order_id].created_at if item.order_id in order_map else item.created_at,
        )
        for item in items
    ]


@router.patch("/items/{item_id}/purchased", response_model=BuyerItemRead)
async def mark_purchased(
    item_id: uuid.UUID,
    body: MarkPurchasedRequest,
    current_user: User = Depends(role_required(*_BUYER_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> BuyerItemRead:
    item = await session.get(ProcurementItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your item")
    if item.status != ProcurementItemStatus.assigned:
        raise HTTPException(status_code=400, detail="Item is not assigned")

    item.quantity_received = body.quantity_received
    item.status = ProcurementItemStatus.purchased
    await session.commit()

    # Re-fetch after commit — attributes are expired post-commit
    refreshed = await session.execute(
        select(ProcurementItem)
        .where(ProcurementItem.id == item_id)
        .options(selectinload(ProcurementItem.catalog_item))
    )
    item = refreshed.scalar_one()

    order_result = await session.execute(
        select(Order)
        .where(Order.id == item.order_id)
        .options(selectinload(Order.restaurant))
    )
    order = order_result.scalar_one_or_none()

    return BuyerItemRead(
        id=item.id,
        order_id=item.order_id,
        display_name=item.display_name,
        quantity_ordered=float(item.quantity_ordered),
        quantity_received=float(item.quantity_received) if item.quantity_received is not None else None,
        unit=item.unit,
        restaurant_name=order.restaurant_name if order else "",
        order_date=order.created_at if order else item.created_at,
    )
