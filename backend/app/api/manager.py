from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import role_required
from app.auth.jwt import create_access_token, create_refresh_token, hash_password
from app.database import get_session
from app.models.order import Order, OrderItem
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.schemas.manager import (
    ManagerOrderRead,
    RestaurantSettingsRead,
    StaffCreate,
    StaffCreateResponse,
    StaffRead,
)
from app.schemas.restaurant import RestaurantSettingsUpdate

router = APIRouter(prefix="/manager", tags=["manager"])

_require_manager = role_required(UserRole.manager)


@router.get("/staff", response_model=list[StaffRead])
async def list_staff(
    current_user: User = Depends(_require_manager),
    session: AsyncSession = Depends(get_session),
) -> list[StaffRead]:
    result = await session.execute(
        select(User).where(
            User.restaurant_id == current_user.restaurant_id,
            User.role.in_([UserRole.cook, UserRole.manager]),
        )
    )
    return result.scalars().all()


@router.post("/staff", response_model=StaffCreateResponse, status_code=201)
async def add_staff(
    body: StaffCreate,
    current_user: User = Depends(_require_manager),
    session: AsyncSession = Depends(get_session),
) -> StaffCreateResponse:
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="Manager not assigned to a restaurant")

    existing = await session.scalar(select(User).where(User.phone == body.phone))
    if existing:
        raise HTTPException(status_code=400, detail="Phone already registered")

    user = User(
        name=body.name,
        phone=body.phone,
        password_hash=hash_password(body.password),
        role=UserRole(body.role),
        restaurant_id=current_user.restaurant_id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return StaffCreateResponse(
        id=user.id,
        name=user.name,
        phone=user.phone,
        role=user.role.value,
        restaurant_id=user.restaurant_id,
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id), user.token_version),
    )


@router.get("/orders", response_model=list[ManagerOrderRead])
async def list_restaurant_orders(
    current_user: User = Depends(_require_manager),
    session: AsyncSession = Depends(get_session),
) -> list[ManagerOrderRead]:
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="Manager not assigned to a restaurant")

    result = await session.execute(
        select(Order, User.name.label("user_name"))
        .join(User, Order.user_id == User.id)
        .where(Order.restaurant_id == current_user.restaurant_id)
        .options(selectinload(Order.items).selectinload(OrderItem.catalog_item))
        .order_by(Order.created_at.desc())
    )
    return [
        ManagerOrderRead(
            id=order.id,
            user_id=order.user_id,
            user_name=user_name,
            restaurant_id=order.restaurant_id,
            status=order.status,
            is_urgent=order.is_urgent,
            deadline=order.deadline,
            created_at=order.created_at,
            items=order.items,
        )
        for order, user_name in result.all()
    ]


@router.get("/settings", response_model=RestaurantSettingsRead)
async def get_settings(
    current_user: User = Depends(_require_manager),
    session: AsyncSession = Depends(get_session),
) -> RestaurantSettingsRead:
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="Manager not assigned to a restaurant")
    rest = await session.get(Restaurant, current_user.restaurant_id)
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return RestaurantSettingsRead(
        restaurant_id=rest.id,
        requires_approval=rest.requires_approval,
    )


@router.patch("/settings", response_model=RestaurantSettingsRead)
async def update_settings(
    body: RestaurantSettingsUpdate,
    current_user: User = Depends(_require_manager),
    session: AsyncSession = Depends(get_session),
) -> RestaurantSettingsRead:
    if not current_user.restaurant_id:
        raise HTTPException(status_code=400, detail="Manager not assigned to a restaurant")
    rest = await session.get(Restaurant, current_user.restaurant_id)
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    rest.requires_approval = body.requires_approval
    await session.commit()
    return RestaurantSettingsRead(
        restaurant_id=rest.id,
        requires_approval=rest.requires_approval,
    )
