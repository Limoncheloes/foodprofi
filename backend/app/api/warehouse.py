from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import role_required
from app.database import get_session
from app.models.catalog import CatalogItem
from app.models.inventory import Inventory, InventoryLog, InventoryReason
from app.models.user import User, UserRole
from app.schemas.inventory import (
    InventoryItemRead,
    StockAdjustRequest,
    StockAdjustResponse,
    StockReceiveRequest,
)
from app.services.stock import receive_stock

router = APIRouter(prefix="/warehouse", tags=["warehouse"])


@router.get("/inventory", response_model=list[InventoryItemRead])
async def list_inventory(
    current_user: User = Depends(role_required(UserRole.warehouse, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> list[InventoryItemRead]:
    result = await session.execute(
        select(Inventory, CatalogItem.name, CatalogItem.unit)
        .join(CatalogItem, Inventory.catalog_item_id == CatalogItem.id)
        .order_by(CatalogItem.name)
    )
    return [
        InventoryItemRead(
            catalog_item_id=inv.catalog_item_id,
            name=name,
            unit=unit.value,
            quantity=inv.quantity,
            updated_at=inv.updated_at,
        )
        for inv, name, unit in result.all()
    ]


@router.post("/inventory/receive", response_model=InventoryItemRead)
async def receive_inventory(
    body: StockReceiveRequest,
    current_user: User = Depends(role_required(UserRole.warehouse, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> InventoryItemRead:
    ci = await session.get(CatalogItem, body.catalog_item_id)
    if not ci:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    inv = await receive_stock(
        session, body.catalog_item_id, body.quantity, current_user.id, body.note
    )
    await session.commit()
    await session.refresh(inv)
    return InventoryItemRead(
        catalog_item_id=inv.catalog_item_id,
        name=ci.name,
        unit=ci.unit.value,
        quantity=inv.quantity,
        updated_at=inv.updated_at,
    )


@router.post("/inventory/adjust", response_model=StockAdjustResponse)
async def adjust_inventory(
    body: StockAdjustRequest,
    current_user: User = Depends(role_required(UserRole.warehouse, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> StockAdjustResponse:
    ci = await session.get(CatalogItem, body.catalog_item_id)
    if not ci:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    result = await session.execute(
        select(Inventory).where(Inventory.catalog_item_id == body.catalog_item_id)
    )
    inv = result.scalar_one_or_none()

    if inv is None:
        inv = Inventory(catalog_item_id=body.catalog_item_id, quantity=body.quantity)
        session.add(inv)
        previous = 0.0
    else:
        previous = inv.quantity
        inv.quantity = body.quantity

    delta = body.quantity - previous
    session.add(InventoryLog(
        catalog_item_id=body.catalog_item_id,
        delta=delta,
        reason=InventoryReason.adjusted,
        user_id=current_user.id,
        note=body.note,
    ))
    await session.commit()
    return StockAdjustResponse(
        catalog_item_id=body.catalog_item_id,
        previous_quantity=previous,
        new_quantity=body.quantity,
    )
