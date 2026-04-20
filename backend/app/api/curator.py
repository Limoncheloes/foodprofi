import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import role_required
from app.database import get_session
from app.models.order import Order
from app.models.procurement import ProcurementItem, ProcurementItemStatus, RoutingRule
from app.models.user import User, UserRole
from app.schemas.curator import (
    AssignRequest,
    CuratorStats,
    PendingItemRead,
    RuleCreate,
    RuleRead,
    RuleUpdate,
)

router = APIRouter(prefix="/curator", tags=["curator"])

_CURATOR_ROLES = (UserRole.curator, UserRole.admin)


@router.get("/stats", response_model=CuratorStats)
async def get_curator_stats(
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> CuratorStats:
    result = await session.execute(
        select(func.count())
        .select_from(ProcurementItem)
        .where(ProcurementItem.status == ProcurementItemStatus.pending_curator)
    )
    count = result.scalar_one()
    return CuratorStats(pending_count=count)


@router.get("/pending", response_model=list[PendingItemRead])
async def list_pending_items(
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> list[PendingItemRead]:
    result = await session.execute(
        select(ProcurementItem)
        .where(ProcurementItem.status == ProcurementItemStatus.pending_curator)
        .options(
            selectinload(ProcurementItem.catalog_item),
        )
        .order_by(ProcurementItem.created_at.asc())
    )
    items = result.scalars().all()

    if not items:
        return []

    # Bulk load orders with restaurants
    order_ids = list({item.order_id for item in items})
    orders_result = await session.execute(
        select(Order)
        .where(Order.id.in_(order_ids))
        .options(selectinload(Order.restaurant))
    )
    order_map = {o.id: o for o in orders_result.scalars().all()}

    return [
        PendingItemRead(
            id=item.id,
            order_id=item.order_id,
            display_name=item.display_name,
            raw_name=item.raw_name,
            quantity_ordered=float(item.quantity_ordered),
            unit=item.unit,
            is_catalog_item=item.is_catalog_item,
            restaurant_name=order_map[item.order_id].restaurant_name if item.order_id in order_map else "",
            created_at=item.created_at,
        )
        for item in items
    ]


@router.post("/assign", response_model=PendingItemRead)
async def assign_item(
    body: AssignRequest,
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> PendingItemRead:
    item = await session.get(
        ProcurementItem, body.item_id,
        options=[selectinload(ProcurementItem.catalog_item)]
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != ProcurementItemStatus.pending_curator:
        raise HTTPException(status_code=400, detail="Item is not pending curator")

    buyer = await session.get(User, body.buyer_id)
    if not buyer or buyer.role not in (UserRole.buyer, UserRole.admin):
        raise HTTPException(status_code=400, detail="Invalid buyer")

    item.buyer_id = body.buyer_id
    item.status = ProcurementItemStatus.assigned
    if body.category_id:
        item.category_id = body.category_id

    # Optionally create routing rule
    if body.save_rule:
        search_name = item.raw_name or item.display_name
        existing = await session.execute(
            select(RoutingRule).where(
                func.lower(RoutingRule.keyword) == search_name.lower()
            )
        )
        rule = existing.scalar_one_or_none()
        if rule:
            rule.buyer_id = body.buyer_id
            if body.category_id:
                rule.category_id = body.category_id
        else:
            rule = RoutingRule(
                keyword=search_name.lower(),
                buyer_id=body.buyer_id,
                category_id=body.category_id,
                created_by_curator=current_user.id,
            )
            session.add(rule)

    await session.commit()

    # Re-fetch item with catalog_item after commit (attributes are expired after commit)
    refreshed = await session.execute(
        select(ProcurementItem)
        .where(ProcurementItem.id == body.item_id)
        .options(selectinload(ProcurementItem.catalog_item))
    )
    item = refreshed.scalar_one()

    order_result = await session.execute(
        select(Order).where(Order.id == item.order_id).options(selectinload(Order.restaurant))
    )
    order = order_result.scalar_one_or_none()

    return PendingItemRead(
        id=item.id,
        order_id=item.order_id,
        display_name=item.display_name,
        raw_name=item.raw_name,
        quantity_ordered=float(item.quantity_ordered),
        unit=item.unit,
        is_catalog_item=item.is_catalog_item,
        restaurant_name=order.restaurant_name if order else "",
        created_at=item.created_at,
    )


@router.get("/rules", response_model=list[RuleRead])
async def list_rules(
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> list[RuleRead]:
    result = await session.execute(
        select(RoutingRule)
        .options(selectinload(RoutingRule.buyer))
        .order_by(RoutingRule.keyword)
    )
    rules = result.scalars().all()
    return [
        RuleRead(
            id=r.id,
            keyword=r.keyword,
            buyer_id=r.buyer_id,
            buyer_name=r.buyer.name if r.buyer else "",
            category_id=r.category_id,
            created_at=r.created_at,
        )
        for r in rules
    ]


@router.post("/rules", response_model=RuleRead, status_code=201)
async def create_rule(
    body: RuleCreate,
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> RuleRead:
    existing = await session.execute(
        select(RoutingRule).where(
            func.lower(RoutingRule.keyword) == body.keyword.lower()
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Rule with this keyword already exists")

    buyer = await session.get(User, body.buyer_id)
    if not buyer or buyer.role not in (UserRole.buyer, UserRole.admin):
        raise HTTPException(status_code=400, detail="Invalid buyer")

    rule = RoutingRule(
        keyword=body.keyword.lower(),
        buyer_id=body.buyer_id,
        category_id=body.category_id,
        created_by_curator=current_user.id,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)

    return RuleRead(
        id=rule.id,
        keyword=rule.keyword,
        buyer_id=rule.buyer_id,
        buyer_name=buyer.name,
        category_id=rule.category_id,
        created_at=rule.created_at,
    )


@router.patch("/rules/{rule_id}", response_model=RuleRead)
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> RuleRead:
    if not body.model_fields_set:
        raise HTTPException(status_code=422, detail="No fields to update")

    rule = await session.get(RoutingRule, rule_id, options=[selectinload(RoutingRule.buyer)])
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if "buyer_id" in body.model_fields_set and body.buyer_id is not None:
        buyer = await session.get(User, body.buyer_id)
        if not buyer or buyer.role not in (UserRole.buyer, UserRole.admin):
            raise HTTPException(status_code=400, detail="Invalid buyer")
        rule.buyer_id = body.buyer_id
        rule.buyer = buyer
    if "category_id" in body.model_fields_set:
        rule.category_id = body.category_id
    await session.commit()
    return RuleRead(
        id=rule.id,
        keyword=rule.keyword,
        buyer_id=rule.buyer_id,
        buyer_name=rule.buyer.name if rule.buyer else "",
        category_id=rule.category_id,
        created_at=rule.created_at,
    )


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> None:
    rule = await session.get(RoutingRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await session.delete(rule)
    await session.commit()


@router.get("/buyers", response_model=list[dict])
async def list_buyers(
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List users with buyer role — for curator UI dropdowns."""
    result = await session.execute(
        select(User).where(User.role == UserRole.buyer).order_by(User.name)
    )
    users = result.scalars().all()
    return [{"id": str(u.id), "name": u.name} for u in users]
