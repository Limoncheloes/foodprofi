from datetime import date as date_type, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import role_required
from app.database import get_session
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole
from app.schemas.aggregation import (
    AggregationSummary,
    MarkPurchasedRequest,
    MarkPurchasedResponse,
)
from app.services.aggregator import get_aggregated_orders
from app.services.stock import receive_stock

router = APIRouter(prefix="/aggregation", tags=["aggregation"])


@router.get("/summary", response_model=AggregationSummary)
async def aggregation_summary(
    target_date: date_type | None = None,
    current_user: User = Depends(role_required(UserRole.buyer, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> AggregationSummary:
    if target_date is None:
        from datetime import date as dt
        target_date = dt.today()
    return await get_aggregated_orders(session, target_date)


@router.post("/mark-purchased", response_model=MarkPurchasedResponse)
async def mark_purchased(
    body: MarkPurchasedRequest,
    current_user: User = Depends(role_required(UserRole.buyer, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> MarkPurchasedResponse:
    # Record purchased quantities in inventory
    for p in body.purchases:
        await receive_stock(
            session, p.catalog_item_id, p.quantity_bought, current_user.id
        )

    # Advance all submitted orders for that date to in_purchase
    start = datetime.combine(body.date, datetime.min.time())
    end = start + timedelta(days=1)

    result = await session.execute(
        select(Order)
        .where(Order.status == OrderStatus.submitted)
        .where(Order.created_at >= start)
        .where(Order.created_at < end)
    )
    orders = result.scalars().all()
    for order in orders:
        order.status = OrderStatus.in_purchase

    await session.commit()
    return MarkPurchasedResponse(
        updated_orders=len(orders),
        purchases_recorded=len(body.purchases),
    )
