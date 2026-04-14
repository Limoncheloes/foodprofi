"""Procurement routing service.

Determines which buyer should handle each procurement item:
1. Catalog items → check category.default_buyer_id
2. Any item → try matching a RoutingRule by keyword
3. No match → status = pending_curator (curator must assign manually)
"""
from typing import Any


def find_best_rule(item_name: str, rules: list[Any]) -> Any | None:
    """Return the RoutingRule with the longest keyword that appears in item_name.

    Matching is case-insensitive substring search.
    Returns None if no rule matches.
    """
    name_lower = item_name.lower()
    matches = [r for r in rules if r.keyword.lower() in name_lower]
    if not matches:
        return None
    return max(matches, key=lambda r: len(r.keyword))


# Status sentinel strings — used in unit tests with MagicMock.
# In production (route_procurement_order), real ProcurementItemStatus enum values are used.
STATUS_ASSIGNED = "assigned"
STATUS_PENDING_CURATOR = "pending_curator"


def apply_routing(item: Any, rules: list[Any]) -> None:
    """Set item.buyer_id, item.category_id, and item.status in-place.

    Priority:
    1. Catalog item with category.default_buyer_id → assign directly
    2. Matching RoutingRule → assign from rule
    3. Nothing matches → pending_curator

    Sets item.status to string sentinels STATUS_ASSIGNED / STATUS_PENDING_CURATOR.
    Callers using real DB objects must map these back to ProcurementItemStatus enum.
    """
    # 1. Catalog item with default buyer on its category
    if item.is_catalog_item and item.catalog_item:
        category = item.catalog_item.category
        if category and category.default_buyer_id:
            item.buyer_id = category.default_buyer_id
            item.category_id = category.id
            item.status = STATUS_ASSIGNED
            return

    # 2. Try routing rules
    search_name = item.raw_name if not item.is_catalog_item else (
        item.catalog_item.name if item.catalog_item else ""
    )
    rule = find_best_rule(search_name, rules)
    if rule:
        item.buyer_id = rule.buyer_id
        if rule.category_id:
            item.category_id = rule.category_id
        item.status = STATUS_ASSIGNED
        return

    # 3. No match
    item.status = STATUS_PENDING_CURATOR


async def route_procurement_order(session, order_id) -> bool:
    """Route all procurement_items for an order. Returns True if all assigned, False if any pending_curator.

    Caller must commit after this call.
    """
    from sqlalchemy import select
    from app.models.procurement import ProcurementItem, RoutingRule, ProcurementItemStatus
    from app.models.catalog import CatalogItem
    from sqlalchemy.orm import selectinload

    # Load all routing rules once
    rules_result = await session.execute(select(RoutingRule))
    rules = rules_result.scalars().all()

    # Load items with eager catalog_item + category
    items_result = await session.execute(
        select(ProcurementItem)
        .where(ProcurementItem.order_id == order_id)
        .options(
            selectinload(ProcurementItem.catalog_item).selectinload(
                CatalogItem.category
            )
        )
    )
    items = items_result.scalars().all()

    for item in items:
        apply_routing(item, rules)
        # Map string sentinels back to real enum values for SQLAlchemy
        if item.status == STATUS_ASSIGNED:
            item.status = ProcurementItemStatus.assigned
        else:
            item.status = ProcurementItemStatus.pending_curator

    all_assigned = all(item.status == ProcurementItemStatus.assigned for item in items)
    return all_assigned
