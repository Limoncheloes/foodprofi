import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory, InventoryLog, InventoryReason


async def receive_stock(
    session: AsyncSession,
    catalog_item_id: uuid.UUID,
    quantity: float,
    user_id: uuid.UUID,
    note: str | None = None,
) -> Inventory:
    """Upsert inventory row and append a received log entry. Caller must commit."""
    result = await session.execute(
        select(Inventory).where(Inventory.catalog_item_id == catalog_item_id)
    )
    inv = result.scalar_one_or_none()

    if inv is None:
        inv = Inventory(catalog_item_id=catalog_item_id, quantity=quantity)
        session.add(inv)
    else:
        inv.quantity += quantity

    session.add(InventoryLog(
        catalog_item_id=catalog_item_id,
        delta=quantity,
        reason=InventoryReason.received,
        user_id=user_id,
        note=note,
    ))
    await session.flush()
    return inv
