import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.database import get_session
from app.models.order import Order, OrderItem, OrderStatus
from app.models.user import User, UserRole
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate
from app.services.stock import consume_order_stock

router = APIRouter(prefix="/orders", tags=["orders"])

# Role-based allowed status transitions
ALLOWED_TRANSITIONS: dict[str, dict[OrderStatus, OrderStatus]] = {
    "buyer": {
        OrderStatus.submitted: OrderStatus.in_purchase,
        OrderStatus.in_purchase: OrderStatus.at_warehouse,
    },
    "warehouse": {
        OrderStatus.at_warehouse: OrderStatus.packed,
        OrderStatus.packed: OrderStatus.in_delivery,
    },
    "driver": {
        OrderStatus.in_delivery: OrderStatus.delivered,
    },
}


@router.post("", response_model=OrderRead, status_code=201)
async def create_order(
    body: OrderCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.role == UserRole.cook and body.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=403, detail="Cooks can only order for their own restaurant")

    order = Order(
        user_id=current_user.id,
        restaurant_id=body.restaurant_id,
        is_urgent=body.is_urgent,
        deadline=body.deadline,
        status=OrderStatus.submitted,
    )
    session.add(order)
    await session.flush()

    for item_data in body.items:
        item = OrderItem(order_id=order.id, **item_data.model_dump())
        session.add(item)

    await session.commit()

    result = await session.execute(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    return result.scalar_one()


@router.get("", response_model=list[OrderRead])
async def list_orders(
    restaurant_id: uuid.UUID | None = None,
    status: OrderStatus | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    q = select(Order).options(selectinload(Order.items))

    if current_user.role == UserRole.cook:
        q = q.where(Order.user_id == current_user.id)
    elif restaurant_id:
        q = q.where(Order.restaurant_id == restaurant_id)

    if status:
        q = q.where(Order.status == status)

    result = await session.execute(q.order_by(Order.created_at.desc()))
    return result.scalars().all()


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current_user.role == UserRole.cook and order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}/status", response_model=OrderRead)
async def update_order_status(
    order_id: uuid.UUID,
    body: OrderStatusUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Admin can cancel any order
    if body.status == OrderStatus.cancelled and current_user.role == UserRole.admin:
        order.status = OrderStatus.cancelled
        await session.commit()
        return order

    transitions = ALLOWED_TRANSITIONS.get(current_user.role.value, {})
    if transitions.get(order.status) != body.status:
        raise HTTPException(status_code=403, detail="Transition not allowed")

    order.status = body.status

    if body.status == OrderStatus.delivered:
        await consume_order_stock(session, order.id, current_user.id)

    await session.commit()
    return order
