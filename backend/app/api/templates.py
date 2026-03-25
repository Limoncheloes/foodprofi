import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import role_required
from app.database import get_session
from app.models.order import Order, OrderItem, OrderStatus
from app.models.template import OrderTemplate, OrderTemplateItem
from app.models.user import User, UserRole
from app.schemas.order import OrderRead
from app.schemas.template import TemplateCreate, TemplateRead

router = APIRouter(prefix="/orders/templates", tags=["templates"])


@router.post("", response_model=TemplateRead, status_code=201)
async def create_template(
    body: TemplateCreate,
    current_user: User = Depends(role_required(UserRole.cook, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> TemplateRead:
    template = OrderTemplate(
        user_id=current_user.id,
        restaurant_id=body.restaurant_id,
        name=body.name,
    )
    session.add(template)
    await session.flush()

    for item in body.items:
        session.add(OrderTemplateItem(template_id=template.id, **item.model_dump()))

    await session.commit()
    result = await session.execute(
        select(OrderTemplate)
        .where(OrderTemplate.id == template.id)
        .options(selectinload(OrderTemplate.items))
    )
    return result.scalar_one()


@router.get("", response_model=list[TemplateRead])
async def list_templates(
    current_user: User = Depends(role_required(UserRole.cook, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> list[TemplateRead]:
    result = await session.execute(
        select(OrderTemplate)
        .where(OrderTemplate.user_id == current_user.id)
        .options(selectinload(OrderTemplate.items))
        .order_by(OrderTemplate.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{template_id}/use", response_model=OrderRead, status_code=201)
async def use_template(
    template_id: uuid.UUID,
    current_user: User = Depends(role_required(UserRole.cook, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> OrderRead:
    result = await session.execute(
        select(OrderTemplate)
        .where(OrderTemplate.id == template_id)
        .where(OrderTemplate.user_id == current_user.id)
        .options(selectinload(OrderTemplate.items))
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    order = Order(
        user_id=current_user.id,
        restaurant_id=template.restaurant_id,
        status=OrderStatus.submitted,
    )
    session.add(order)
    await session.flush()

    for ti in template.items:
        session.add(OrderItem(
            order_id=order.id,
            catalog_item_id=ti.catalog_item_id,
            quantity=ti.quantity,
            variant=ti.variant,
            note=ti.note,
        ))

    await session.commit()
    result = await session.execute(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    return result.scalar_one()
