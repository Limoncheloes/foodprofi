import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import role_required
from app.auth.jwt import create_access_token, create_refresh_token, hash_password
from app.database import get_session
from app.models.catalog import Category
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.schemas.catalog import CategoryRead
from app.schemas.restaurant import RestaurantCreate, RestaurantRead
from app.schemas.user import AdminCreateUserRequest, CreateUserResponse, UserRead

router = APIRouter(prefix="/admin", tags=["admin"],
                   dependencies=[Depends(role_required(UserRole.admin, UserRole.curator))])


@router.get("/users", response_model=list[UserRead])
async def list_users(role: str | None = None, session: AsyncSession = Depends(get_session)):
    q = select(User)
    if role:
        try:
            q = q.where(User.role == UserRole(role))
        except ValueError:
            raise HTTPException(400, detail=f"Invalid role: {role}")
    result = await session.execute(q)
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


@router.post("/users", response_model=CreateUserResponse, status_code=201)
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

    return CreateUserResponse(
        access_token=create_access_token(str(user.id), user.role.value, user.token_version),
        refresh_token=create_refresh_token(str(user.id), user.token_version),
        user=UserRead.model_validate(user),
    )


class CategoryBuyerUpdate(BaseModel):
    default_buyer_id: uuid.UUID | None


@router.patch("/categories/{category_id}/buyer", response_model=CategoryRead,
              dependencies=[Depends(role_required(UserRole.admin))])
async def set_category_default_buyer(
    category_id: uuid.UUID,
    body: CategoryBuyerUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Set or clear the default buyer for a category (used in auto-routing)."""
    cat = await session.get(Category, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    if body.default_buyer_id:
        buyer = await session.get(User, body.default_buyer_id)
        if not buyer or buyer.role not in (UserRole.buyer, UserRole.admin):
            raise HTTPException(status_code=400, detail="Invalid buyer")
    cat.default_buyer_id = body.default_buyer_id
    await session.commit()
    await session.refresh(cat)
    return cat
