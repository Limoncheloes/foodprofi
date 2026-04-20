import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user, role_required
from app.limiter import limiter
from app.database import get_session
from app.models.order import Order, OrderItem, OrderStatus
from app.models.procurement import ProcurementItem
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate
from app.services.documents import generate_docx, generate_xlsx
from app.services.stock import consume_order_stock

router = APIRouter(prefix="/orders", tags=["orders"])

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

_ORDER_OPTIONS = [
    selectinload(Order.user),
    selectinload(Order.restaurant),
    selectinload(Order.items).selectinload(OrderItem.catalog_item),
]


@router.post("", response_model=OrderRead, status_code=201)
async def create_order(
    body: OrderCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.role == UserRole.cook and body.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=403, detail="Cooks can only order for their own restaurant")

    restaurant = await session.get(Restaurant, body.restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    initial_status = (
        OrderStatus.pending_approval
        if restaurant.requires_approval
        else OrderStatus.submitted
    )

    order = Order(
        user_id=current_user.id,
        restaurant_id=body.restaurant_id,
        is_urgent=body.is_urgent,
        deadline=body.deadline,
        status=initial_status,
    )
    session.add(order)
    await session.flush()

    for item_data in body.items:
        item = OrderItem(order_id=order.id, **item_data.model_dump())
        session.add(item)

    await session.commit()

    result = await session.execute(
        select(Order).where(Order.id == order.id).options(*_ORDER_OPTIONS)
    )
    return result.scalar_one()


@router.get("", response_model=list[OrderRead])
async def list_orders(
    restaurant_id: uuid.UUID | None = None,
    status: OrderStatus | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    q = select(Order).options(*_ORDER_OPTIONS)

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
        select(Order).where(Order.id == order_id).options(*_ORDER_OPTIONS)
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
        select(Order).where(Order.id == order_id).options(*_ORDER_OPTIONS)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if body.status == OrderStatus.cancelled and current_user.role == UserRole.admin:
        order.status = OrderStatus.cancelled
        await session.commit()
        return order

    if current_user.role == UserRole.manager:
        if current_user.restaurant_id != order.restaurant_id:
            raise HTTPException(status_code=403, detail="Order belongs to a different restaurant")
        if order.status != OrderStatus.pending_approval:
            raise HTTPException(status_code=403, detail="Only pending_approval orders can be approved or rejected")
        if body.status not in (OrderStatus.submitted, OrderStatus.cancelled):
            raise HTTPException(status_code=403, detail="Manager can only approve (submitted) or reject (cancelled)")
        order.status = body.status
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


async def _load_export_items(session, order_id):
    """Load procurement items with buyer and category names for export."""
    result = await session.execute(
        select(ProcurementItem)
        .where(ProcurementItem.order_id == order_id)
        .options(
            selectinload(ProcurementItem.catalog_item),
            selectinload(ProcurementItem.category),
            selectinload(ProcurementItem.buyer),
        )
        .order_by(ProcurementItem.buyer_id, ProcurementItem.created_at)
    )
    items = result.scalars().all()

    class ExportItem:
        def __init__(self, pi):
            self.display_name = pi.display_name
            self.quantity_ordered = pi.quantity_ordered
            self.quantity_received = pi.quantity_received
            self.unit = pi.unit
            self.buyer_name = pi.buyer.name if pi.buyer else "Не назначен"
            self.category_name = pi.category.name if pi.category else ""
            self.substitution_note = pi.substitution_note
            self.is_catalog_item = pi.is_catalog_item
            self.raw_name = pi.raw_name

    return [ExportItem(i) for i in items]


@router.get("/{order_id}/export/docx")
@limiter.limit("10/minute")
async def export_order_docx(
    request: Request,
    order_id: uuid.UUID,
    current_user=Depends(role_required(UserRole.curator, UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current_user.role == UserRole.manager and order.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    items = await _load_export_items(session, order_id)
    if not items:
        raise HTTPException(status_code=400, detail="Order has no procurement items")

    docx_bytes = generate_docx(order, items)
    filename = f"zakupka_{str(order_id)[:8]}.docx"
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{order_id}/export/xlsx")
@limiter.limit("10/minute")
async def export_order_xlsx(
    request: Request,
    order_id: uuid.UUID,
    current_user=Depends(role_required(UserRole.curator, UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current_user.role == UserRole.manager and order.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    items = await _load_export_items(session, order_id)
    if not items:
        raise HTTPException(status_code=400, detail="Order has no procurement items")

    missing = [i.display_name for i in items if i.quantity_received is None]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot export: missing quantity_received for: {', '.join(missing[:3])}"
                   + ("..." if len(missing) > 3 else ""),
        )

    xlsx_bytes = generate_xlsx(order, items)
    filename = f"1c_zakupka_{str(order_id)[:8]}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
