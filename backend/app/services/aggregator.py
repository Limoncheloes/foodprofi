import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import CatalogItem, Category
from app.models.inventory import Inventory
from app.models.order import Order, OrderStatus
from app.schemas.aggregation import (
    AggregationCategoryRead,
    AggregationItemRead,
    AggregationSummary,
    RestaurantNeed,
)


async def get_aggregated_orders(
    session: AsyncSession, target_date: date
) -> AggregationSummary:
    """
    Collect submitted + in_purchase orders for target_date,
    group by category → item, subtract current inventory.
    """
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)

    orders_result = await session.execute(
        select(Order)
        .where(Order.status.in_([OrderStatus.submitted, OrderStatus.in_purchase]))
        .where(Order.created_at >= start)
        .where(Order.created_at < end)
        .options(selectinload(Order.items))
    )
    orders = orders_result.scalars().all()

    item_ids: set[uuid.UUID] = {oi.catalog_item_id for o in orders for oi in o.items}
    if not item_ids:
        return AggregationSummary(date=target_date, categories=[])

    # Load catalog items
    ci_result = await session.execute(
        select(CatalogItem).where(CatalogItem.id.in_(item_ids))
    )
    catalog_items: dict[uuid.UUID, CatalogItem] = {
        ci.id: ci for ci in ci_result.scalars().all()
    }

    # Load categories (sorted)
    cat_ids = {ci.category_id for ci in catalog_items.values()}
    cats_result = await session.execute(
        select(Category).where(Category.id.in_(cat_ids)).order_by(Category.sort_order)
    )
    categories: dict[uuid.UUID, Category] = {c.id: c for c in cats_result.scalars().all()}

    # Load inventory (current stock levels)
    inv_result = await session.execute(
        select(Inventory).where(Inventory.catalog_item_id.in_(item_ids))
    )
    inventory: dict[uuid.UUID, float] = {
        inv.catalog_item_id: inv.quantity for inv in inv_result.scalars().all()
    }

    # Aggregate by category → item
    agg: dict[uuid.UUID, dict[uuid.UUID, dict]] = {}
    for order in orders:
        for oi in order.items:
            ci = catalog_items.get(oi.catalog_item_id)
            if not ci:
                continue
            cat_id, item_id = ci.category_id, oi.catalog_item_id
            agg.setdefault(cat_id, {}).setdefault(
                item_id, {"total": 0.0, "restaurants": []}
            )
            agg[cat_id][item_id]["total"] += oi.quantity
            agg[cat_id][item_id]["restaurants"].append(
                RestaurantNeed(
                    restaurant_id=order.restaurant_id,
                    quantity=oi.quantity,
                    variant=oi.variant,
                )
            )

    # Build response sorted by category.sort_order
    result_cats = []
    for cat_id, items in sorted(
        agg.items(), key=lambda x: categories[x[0]].sort_order
    ):
        cat = categories[cat_id]
        cat_items = [
            AggregationItemRead(
                catalog_item_id=item_id,
                name=catalog_items[item_id].name,
                unit=catalog_items[item_id].unit.value,
                total_needed=data["total"],
                in_stock=inventory.get(item_id, 0.0),
                to_buy=max(0.0, data["total"] - inventory.get(item_id, 0.0)),
                restaurants=data["restaurants"],
            )
            for item_id, data in items.items()
        ]
        result_cats.append(
            AggregationCategoryRead(
                category_id=cat_id,
                category_name=cat.name,
                items=cat_items,
            )
        )

    return AggregationSummary(date=target_date, categories=result_cats)
