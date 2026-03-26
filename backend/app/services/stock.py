import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory, InventoryLog, InventoryReason
from app.models.order import OrderItem


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


async def consume_order_stock(
    session: AsyncSession,
    order_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Deduct each order item's quantity from inventory when an order is delivered.

    Creates negative inventory if stock is insufficient. Caller must commit.
    """
    result = await session.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )
    items = result.scalars().all()

    for item in items:
        inv_result = await session.execute(
            select(Inventory).where(Inventory.catalog_item_id == item.catalog_item_id)
        )
        inv = inv_result.scalar_one_or_none()

        if inv is None:
            inv = Inventory(catalog_item_id=item.catalog_item_id, quantity=-item.quantity)
            session.add(inv)
        else:
            inv.quantity -= item.quantity

        session.add(
            InventoryLog(
                catalog_item_id=item.catalog_item_id,
                delta=-item.quantity,
                reason=InventoryReason.consumed,
                user_id=user_id,
                note=f"order:{order_id}",
            )
        )

    await session.flush()
