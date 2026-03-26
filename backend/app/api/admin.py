import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel as _PydanticBase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import role_required
from app.auth.jwt import create_access_token, create_refresh_token, hash_password
from app.database import get_session
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.schemas.restaurant import RestaurantCreate, RestaurantRead
from app.schemas.user import AdminCreateUserRequest, UserRead

router = APIRouter(prefix="/admin", tags=["admin"],
                   dependencies=[Depends(role_required(UserRole.admin))])


class _CreateUserResponse(_PydanticBase):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead


@router.get("/users", response_model=list[UserRead])
async def list_users(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User))
    return result.scalars().all()


@router.get("/restaurants", response_model=list[RestaurantRead])
async def list_restaurants(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Restaurant))
    return result.scalars().all()


@router.post("/restaurants", response_model=RestaurantRead, status_code=201)
async def create_restaurant(body: RestaurantCreate, session: AsyncSession = Depends(get_session)):
    rest = Restaurant(**body.model_dump())
    session.add(rest)
    await session.commit()
    await session.refresh(rest)
    return rest


@router.patch("/restaurants/{rest_id}", response_model=RestaurantRead)
async def update_restaurant(
    rest_id: uuid.UUID,
    body: RestaurantCreate,
    session: AsyncSession = Depends(get_session),
):
    rest = await session.get(Restaurant, rest_id)
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    for field, value in body.model_dump().items():
        setattr(rest, field, value)
    await session.commit()
    await session.refresh(rest)
    return rest


@router.post("/users", response_model=_CreateUserResponse, status_code=201)
async def create_user(body: AdminCreateUserRequest, session: AsyncSession = Depends(get_session)):
    existing = await session.scalar(select(User).where(User.phone == body.phone))
    if existing:
        raise HTTPException(status_code=400, detail="Phone already registered")

    user = User(
        name=body.name,
        phone=body.phone,
        password_hash=hash_password(body.password),
        role=body.role,
        restaurant_id=body.restaurant_id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return _CreateUserResponse(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id), user.token_version),
        user=UserRead.model_validate(user),
    )
