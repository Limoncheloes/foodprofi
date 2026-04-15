import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import role_required
from app.database import get_session
from app.models.catalog import CatalogItem, Category
from app.models.user import UserRole
from app.schemas.catalog import (
    CatalogItemCreate,
    CatalogItemRead,
    CatalogItemUpdate,
    CategoryCreate,
    CategoryRead,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/categories", response_model=list[CategoryRead])
async def list_categories(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Category).order_by(Category.sort_order))
    return result.scalars().all()


@router.post("/categories", response_model=CategoryRead, status_code=201,
             dependencies=[Depends(role_required(UserRole.admin))])
async def create_category(body: CategoryCreate, session: AsyncSession = Depends(get_session)):
    cat = Category(**body.model_dump())
    session.add(cat)
    await session.commit()
    await session.refresh(cat)
    return cat


@router.get("/items", response_model=list[CatalogItemRead])
async def list_items(
    category_id: uuid.UUID | None = None,
    search: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    q = select(CatalogItem).where(CatalogItem.is_active == True)  # noqa: E712
    if category_id:
        q = q.where(CatalogItem.category_id == category_id)
    if search:
        q = q.where(CatalogItem.name.ilike(f"%{search}%"))
    result = await session.execute(q)
    return result.scalars().all()


@router.post("/items", response_model=CatalogItemRead, status_code=201,
             dependencies=[Depends(role_required(UserRole.admin))])
async def create_item(body: CatalogItemCreate, session: AsyncSession = Depends(get_session)):
    item = CatalogItem(**body.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.patch("/items/{item_id}", response_model=CatalogItemRead,
              dependencies=[Depends(role_required(UserRole.admin))])
async def update_item(
    item_id: uuid.UUID,
    body: CatalogItemUpdate,
    session: AsyncSession = Depends(get_session),
):
    item = await session.get(CatalogItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    await session.commit()
    await session.refresh(item)
    return item
