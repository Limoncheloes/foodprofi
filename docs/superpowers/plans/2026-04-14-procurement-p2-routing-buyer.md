# Procurement P2 — Routing & Buyer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать интерфейс куратора (очередь непереданных позиций, ручное назначение, управление правилами маршрутизации) и интерфейс закупщика (список своих позиций, внесение фактического количества).

**Architecture:** Два новых роутера — `/curator` и `/buyer/procurement`. Куратор назначает `buyer_id` на `ProcurementItem`, опционально создавая `RoutingRule`. Закупщик видит только свои `ProcurementItem` и обновляет `quantity_received` + `status`. Бейдж куратора — через `GET /curator/stats`.

**Tech Stack:** Python FastAPI + SQLAlchemy 2 async | Next.js 14 App Router + TypeScript + shadcn/ui | PostgreSQL | pytest + httpx

**Prerequisite:** P1 план полностью выполнен.

---

## File Map

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `backend/app/schemas/curator.py` | Pydantic схемы: AssignRequest, RuleCreate, RuleRead, CuratorStats |
| `backend/app/schemas/buyer_procurement.py` | Pydantic схемы: BuyerItemRead, BuyerItemUpdate |
| `backend/app/api/curator.py` | Роутер `/curator`: pending queue, assign, rules CRUD, stats |
| `backend/app/api/buyer_procurement.py` | Роутер `/buyer/procurement`: items, update, summary |
| `backend/tests/test_curator.py` | Интеграционные тесты /curator API |
| `backend/tests/test_buyer_procurement.py` | Интеграционные тесты /buyer/procurement API |

### Backend — Modified Files
| File | Change |
|------|--------|
| `backend/app/main.py` | Зарегистрировать curator и buyer_procurement роутеры |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/app/(curator)/curator/queue/page.tsx` | Очередь позиций ожидающих куратора |
| `frontend/src/app/(curator)/curator/rules/page.tsx` | Управление правилами маршрутизации |
| `frontend/src/app/(buyer)/buyer/procurement/page.tsx` | Позиции закупщика на сегодня |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `frontend/src/lib/types.ts` | Добавить RuleRead, CuratorStats, BuyerItemUpdate типы |

---

## Task 1: Curator Schemas & API

**Files:**
- Create: `backend/app/schemas/curator.py`
- Create: `backend/app/api/curator.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Создать `backend/app/schemas/curator.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class AssignRequest(BaseModel):
    item_id: uuid.UUID
    buyer_id: uuid.UUID
    category_id: uuid.UUID | None = None
    save_rule: bool = False   # if True → also create/update RoutingRule


class RuleCreate(BaseModel):
    keyword: str
    buyer_id: uuid.UUID
    category_id: uuid.UUID | None = None


class RuleUpdate(BaseModel):
    buyer_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None


class RuleRead(BaseModel):
    id: uuid.UUID
    keyword: str
    buyer_id: uuid.UUID
    buyer_name: str
    category_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CuratorStats(BaseModel):
    pending_count: int


class PendingItemRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    display_name: str
    raw_name: str | None
    quantity_ordered: float
    unit: str
    is_catalog_item: bool
    restaurant_name: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Создать `backend/app/api/curator.py`**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import role_required
from app.database import get_session
from app.models.order import Order
from app.models.procurement import ProcurementItem, ProcurementItemStatus, RoutingRule
from app.models.user import User, UserRole
from app.schemas.curator import (
    AssignRequest,
    CuratorStats,
    PendingItemRead,
    RuleCreate,
    RuleRead,
    RuleUpdate,
)

router = APIRouter(prefix="/curator", tags=["curator"])

_CURATOR_ROLES = (UserRole.curator, UserRole.admin)


@router.get("/stats", response_model=CuratorStats)
async def get_curator_stats(
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> CuratorStats:
    result = await session.execute(
        select(func.count()).where(
            ProcurementItem.status == ProcurementItemStatus.pending_curator
        )
    )
    count = result.scalar_one()
    return CuratorStats(pending_count=count)


@router.get("/pending", response_model=list[PendingItemRead])
async def list_pending_items(
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> list[PendingItemRead]:
    result = await session.execute(
        select(ProcurementItem)
        .where(ProcurementItem.status == ProcurementItemStatus.pending_curator)
        .options(
            selectinload(ProcurementItem.catalog_item),
        )
        .order_by(ProcurementItem.created_at.asc())
    )
    items = result.scalars().all()

    # Load restaurant names via order
    response = []
    for item in items:
        order_result = await session.execute(
            select(Order)
            .where(Order.id == item.order_id)
            .options(selectinload(Order.restaurant))
        )
        order = order_result.scalar_one_or_none()
        restaurant_name = order.restaurant_name if order else ""
        response.append(
            PendingItemRead(
                id=item.id,
                order_id=item.order_id,
                display_name=item.display_name,
                raw_name=item.raw_name,
                quantity_ordered=float(item.quantity_ordered),
                unit=item.unit,
                is_catalog_item=item.is_catalog_item,
                restaurant_name=restaurant_name,
                created_at=item.created_at,
            )
        )
    return response


@router.post("/assign", response_model=PendingItemRead)
async def assign_item(
    body: AssignRequest,
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> PendingItemRead:
    item = await session.get(
        ProcurementItem, body.item_id,
        options=[selectinload(ProcurementItem.catalog_item)]
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != ProcurementItemStatus.pending_curator:
        raise HTTPException(status_code=400, detail="Item is not pending curator")

    buyer = await session.get(User, body.buyer_id)
    if not buyer or buyer.role not in (UserRole.buyer, UserRole.admin):
        raise HTTPException(status_code=400, detail="Invalid buyer")

    item.buyer_id = body.buyer_id
    item.status = ProcurementItemStatus.assigned
    if body.category_id:
        item.category_id = body.category_id

    # Optionally create routing rule
    if body.save_rule:
        search_name = item.raw_name or item.display_name
        existing = await session.execute(
            select(RoutingRule).where(
                func.lower(RoutingRule.keyword) == search_name.lower()
            )
        )
        rule = existing.scalar_one_or_none()
        if rule:
            rule.buyer_id = body.buyer_id
            if body.category_id:
                rule.category_id = body.category_id
        else:
            rule = RoutingRule(
                keyword=search_name.lower(),
                buyer_id=body.buyer_id,
                category_id=body.category_id,
                created_by_curator=current_user.id,
            )
            session.add(rule)

    await session.commit()

    order_result = await session.execute(
        select(Order).where(Order.id == item.order_id).options(selectinload(Order.restaurant))
    )
    order = order_result.scalar_one_or_none()

    return PendingItemRead(
        id=item.id,
        order_id=item.order_id,
        display_name=item.display_name,
        raw_name=item.raw_name,
        quantity_ordered=float(item.quantity_ordered),
        unit=item.unit,
        is_catalog_item=item.is_catalog_item,
        restaurant_name=order.restaurant_name if order else "",
        created_at=item.created_at,
    )


@router.get("/rules", response_model=list[RuleRead])
async def list_rules(
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> list[RuleRead]:
    result = await session.execute(
        select(RoutingRule)
        .options(selectinload(RoutingRule.buyer))
        .order_by(RoutingRule.keyword)
    )
    rules = result.scalars().all()
    return [
        RuleRead(
            id=r.id,
            keyword=r.keyword,
            buyer_id=r.buyer_id,
            buyer_name=r.buyer.name if r.buyer else "",
            category_id=r.category_id,
            created_at=r.created_at,
        )
        for r in rules
    ]


@router.post("/rules", response_model=RuleRead, status_code=201)
async def create_rule(
    body: RuleCreate,
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> RuleRead:
    existing = await session.execute(
        select(RoutingRule).where(
            func.lower(RoutingRule.keyword) == body.keyword.lower()
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Rule with this keyword already exists")

    buyer = await session.get(User, body.buyer_id)
    if not buyer or buyer.role not in (UserRole.buyer, UserRole.admin):
        raise HTTPException(status_code=400, detail="Invalid buyer")

    rule = RoutingRule(
        keyword=body.keyword.lower(),
        buyer_id=body.buyer_id,
        category_id=body.category_id,
        created_by_curator=current_user.id,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)

    return RuleRead(
        id=rule.id,
        keyword=rule.keyword,
        buyer_id=rule.buyer_id,
        buyer_name=buyer.name,
        category_id=rule.category_id,
        created_at=rule.created_at,
    )


@router.patch("/rules/{rule_id}", response_model=RuleRead)
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> RuleRead:
    rule = await session.get(RoutingRule, rule_id, options=[selectinload(RoutingRule.buyer)])
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if body.buyer_id:
        buyer = await session.get(User, body.buyer_id)
        if not buyer or buyer.role not in (UserRole.buyer, UserRole.admin):
            raise HTTPException(status_code=400, detail="Invalid buyer")
        rule.buyer_id = body.buyer_id
        rule.buyer = buyer
    if body.category_id is not None:
        rule.category_id = body.category_id
    await session.commit()
    return RuleRead(
        id=rule.id,
        keyword=rule.keyword,
        buyer_id=rule.buyer_id,
        buyer_name=rule.buyer.name if rule.buyer else "",
        category_id=rule.category_id,
        created_at=rule.created_at,
    )


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(role_required(*_CURATOR_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> None:
    rule = await session.get(RoutingRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await session.delete(rule)
    await session.commit()
```

- [ ] **Step 3: Зарегистрировать роутер в `backend/app/main.py`**

Прочитай файл. Добавь:

```python
from app.api.curator import router as curator_router
# ...
app.include_router(curator_router)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/curator.py \
        backend/app/api/curator.py \
        backend/app/main.py
git commit -m "feat: add /curator API (queue, assign, rules CRUD)"
```

---

## Task 2: Curator API Tests

**Files:**
- Create: `backend/tests/test_curator.py`

- [ ] **Step 1: Написать failing tests — `backend/tests/test_curator.py`**

```python
"""Integration tests for /curator API."""
from httpx import AsyncClient


async def register(client: AsyncClient, phone: str, role: str, rest_id: str | None = None) -> dict:
    body = {"phone": phone, "password": "pass123", "name": "U", "role": role}
    if rest_id:
        body["restaurant_id"] = rest_id
    resp = await client.post("/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def setup(client: AsyncClient, admin: dict) -> tuple[dict, dict, str, str]:
    """Returns (curator_headers, buyer_headers, rest_id, raw_item_order_id)."""
    cat = await client.post("/catalog/categories", json={"name": "Прочее", "sort_order": 9}, headers=admin)
    rest = await client.post(
        "/admin/restaurants",
        json={"name": "Тест", "address": "ул. 1", "contact_phone": "+99670000099"},
        headers=admin,
    )
    rest_id = rest.json()["id"]
    cook = await register(client, "+99672000001", "cook", rest_id)
    curator = await register(client, "+99672000002", "curator")
    buyer = await register(client, "+99672000003", "buyer")

    # Create order with raw_name item (will be pending_curator)
    order = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [{"raw_name": "Ложки деревянные", "quantity_ordered": "50", "unit": "шт"}],
        },
        headers=cook,
    )
    assert order.status_code == 201
    order_id = order.json()["id"]
    await client.post(f"/kitchen/orders/{order_id}/submit", headers=cook)

    return curator, buyer, rest_id, order_id


async def test_curator_sees_pending_items(client: AsyncClient, admin_token: dict):
    curator, _, _, _ = await setup(client, admin_token)
    resp = await client.get("/curator/pending", headers=curator)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["raw_name"] == "Ложки деревянные"


async def test_cook_cannot_access_curator_queue(client: AsyncClient, admin_token: dict):
    _, _, rest_id, _ = await setup(client, admin_token)
    cook = await register(client, "+99672000010", "cook", rest_id)
    resp = await client.get("/curator/pending", headers=cook)
    assert resp.status_code == 403


async def test_curator_stats_returns_count(client: AsyncClient, admin_token: dict):
    curator, _, _, _ = await setup(client, admin_token)
    resp = await client.get("/curator/stats", headers=curator)
    assert resp.status_code == 200
    assert resp.json()["pending_count"] >= 1


async def test_assign_item_to_buyer(client: AsyncClient, admin_token: dict):
    curator, buyer_headers, _, order_id = await setup(client, admin_token)

    # Get the pending item id
    pending = await client.get("/curator/pending", headers=curator)
    item_id = pending.json()[0]["id"]

    # Get buyer's user id
    from app.auth.jwt import decode_token
    buyer_token = buyer_headers["Authorization"].split(" ")[1]
    buyer_id = decode_token(buyer_token)["sub"]

    resp = await client.post(
        "/curator/assign",
        json={"item_id": item_id, "buyer_id": buyer_id, "save_rule": False},
        headers=curator,
    )
    assert resp.status_code == 200

    # Item should no longer be in pending queue
    pending2 = await client.get("/curator/pending", headers=curator)
    assert len(pending2.json()) == 0


async def test_assign_with_save_rule_creates_rule(client: AsyncClient, admin_token: dict):
    curator, buyer_headers, _, _ = await setup(client, admin_token)
    pending = await client.get("/curator/pending", headers=curator)
    item_id = pending.json()[0]["id"]

    from app.auth.jwt import decode_token
    buyer_id = decode_token(buyer_headers["Authorization"].split(" ")[1])["sub"]

    await client.post(
        "/curator/assign",
        json={"item_id": item_id, "buyer_id": buyer_id, "save_rule": True},
        headers=curator,
    )

    rules = await client.get("/curator/rules", headers=curator)
    assert rules.status_code == 200
    assert len(rules.json()) == 1
    assert "ложки" in rules.json()[0]["keyword"]


async def test_create_rule_manually(client: AsyncClient, admin_token: dict):
    curator, buyer_headers, _, _ = await setup(client, admin_token)

    from app.auth.jwt import decode_token
    buyer_id = decode_token(buyer_headers["Authorization"].split(" ")[1])["sub"]

    resp = await client.post(
        "/curator/rules",
        json={"keyword": "говядина", "buyer_id": buyer_id},
        headers=curator,
    )
    assert resp.status_code == 201
    assert resp.json()["keyword"] == "говядина"


async def test_create_duplicate_rule_rejected(client: AsyncClient, admin_token: dict):
    curator, buyer_headers, _, _ = await setup(client, admin_token)

    from app.auth.jwt import decode_token
    buyer_id = decode_token(buyer_headers["Authorization"].split(" ")[1])["sub"]

    await client.post(
        "/curator/rules",
        json={"keyword": "молоко", "buyer_id": buyer_id},
        headers=curator,
    )
    resp = await client.post(
        "/curator/rules",
        json={"keyword": "молоко", "buyer_id": buyer_id},
        headers=curator,
    )
    assert resp.status_code == 400


async def test_delete_rule(client: AsyncClient, admin_token: dict):
    curator, buyer_headers, _, _ = await setup(client, admin_token)

    from app.auth.jwt import decode_token
    buyer_id = decode_token(buyer_headers["Authorization"].split(" ")[1])["sub"]

    create_resp = await client.post(
        "/curator/rules",
        json={"keyword": "картофель", "buyer_id": buyer_id},
        headers=curator,
    )
    rule_id = create_resp.json()["id"]
    del_resp = await client.delete(f"/curator/rules/{rule_id}", headers=curator)
    assert del_resp.status_code == 204

    rules = await client.get("/curator/rules", headers=curator)
    assert all(r["id"] != rule_id for r in rules.json())
```

- [ ] **Step 2: Запустить тесты — ожидать PASS**

```bash
docker compose exec backend pytest tests/test_curator.py -v
```

Ожидаемый результат: 8 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_curator.py
git commit -m "test: add curator API tests"
```

---

## Task 3: Buyer Procurement API

**Files:**
- Create: `backend/app/schemas/buyer_procurement.py`
- Create: `backend/app/api/buyer_procurement.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Создать `backend/app/schemas/buyer_procurement.py`**

```python
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BuyerItemRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    display_name: str
    raw_name: str | None
    quantity_ordered: float
    quantity_received: float | None
    unit: str
    status: str
    category_id: uuid.UUID | None
    curator_note: str | None
    substitution_note: str | None
    restaurant_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BuyerItemUpdate(BaseModel):
    quantity_received: Decimal | None = None
    status: str | None = None          # "purchased" | "not_found" | "substituted"
    substitution_note: str | None = None

    def validate_status(self):
        allowed = {"purchased", "not_found", "substituted"}
        if self.status and self.status not in allowed:
            raise ValueError(f"status must be one of {allowed}")


class BuyerSummaryItem(BaseModel):
    category_name: str
    display_name: str
    quantity_ordered: float
    quantity_received: float | None
    unit: str
    status: str
```

- [ ] **Step 2: Создать `backend/app/api/buyer_procurement.py`**

```python
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import role_required
from app.database import get_session
from app.models.catalog import Category
from app.models.order import Order
from app.models.procurement import ProcurementItem, ProcurementItemStatus
from app.models.user import User, UserRole
from app.schemas.buyer_procurement import BuyerItemRead, BuyerItemUpdate, BuyerSummaryItem

router = APIRouter(prefix="/buyer/procurement", tags=["buyer-procurement"])

_BUYER_ROLES = (UserRole.buyer, UserRole.admin)


def _item_to_read(item: ProcurementItem, restaurant_name: str) -> BuyerItemRead:
    return BuyerItemRead(
        id=item.id,
        order_id=item.order_id,
        display_name=item.display_name,
        raw_name=item.raw_name,
        quantity_ordered=float(item.quantity_ordered),
        quantity_received=float(item.quantity_received) if item.quantity_received is not None else None,
        unit=item.unit,
        status=item.status.value,
        category_id=item.category_id,
        curator_note=item.curator_note,
        substitution_note=item.substitution_note,
        restaurant_name=restaurant_name,
        created_at=item.created_at,
    )


@router.get("/items", response_model=list[BuyerItemRead])
async def list_buyer_items(
    target_date: date | None = None,
    status: str | None = None,
    current_user: User = Depends(role_required(*_BUYER_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> list[BuyerItemRead]:
    """List procurement items assigned to this buyer, optionally filtered by date and status."""
    q = (
        select(ProcurementItem)
        .options(selectinload(ProcurementItem.catalog_item))
        .order_by(ProcurementItem.created_at.asc())
    )
    if current_user.role == UserRole.buyer:
        q = q.where(ProcurementItem.buyer_id == current_user.id)

    if status:
        try:
            q = q.where(ProcurementItem.status == ProcurementItemStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    result = await session.execute(q)
    items = result.scalars().all()

    # Filter by date if provided
    if target_date:
        items = [
            i for i in items
            if i.created_at.date() == target_date
        ]

    response = []
    for item in items:
        order_result = await session.execute(
            select(Order).where(Order.id == item.order_id).options(selectinload(Order.restaurant))
        )
        order = order_result.scalar_one_or_none()
        restaurant_name = order.restaurant_name if order else ""
        response.append(_item_to_read(item, restaurant_name))
    return response


@router.patch("/items/{item_id}", response_model=BuyerItemRead)
async def update_buyer_item(
    item_id: uuid.UUID,
    body: BuyerItemUpdate,
    current_user: User = Depends(role_required(*_BUYER_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> BuyerItemRead:
    item = await session.get(
        ProcurementItem, item_id,
        options=[selectinload(ProcurementItem.catalog_item)]
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if current_user.role == UserRole.buyer and item.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your item")
    if item.status not in (ProcurementItemStatus.assigned, ProcurementItemStatus.purchased,
                            ProcurementItemStatus.not_found, ProcurementItemStatus.substituted):
        raise HTTPException(status_code=400, detail="Item cannot be updated in current status")

    if body.quantity_received is not None:
        item.quantity_received = float(body.quantity_received)
    if body.status is not None:
        body.validate_status()
        item.status = ProcurementItemStatus(body.status)
    if body.substitution_note is not None:
        item.substitution_note = body.substitution_note

    await session.commit()

    order_result = await session.execute(
        select(Order).where(Order.id == item.order_id).options(selectinload(Order.restaurant))
    )
    order = order_result.scalar_one_or_none()
    return _item_to_read(item, order.restaurant_name if order else "")


@router.get("/summary", response_model=list[BuyerSummaryItem])
async def get_buyer_summary(
    target_date: date | None = None,
    current_user: User = Depends(role_required(*_BUYER_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> list[BuyerSummaryItem]:
    """Aggregated view grouped by category for printing/planning."""
    q = (
        select(ProcurementItem)
        .options(
            selectinload(ProcurementItem.catalog_item),
            selectinload(ProcurementItem.category),
        )
        .order_by(ProcurementItem.category_id, ProcurementItem.created_at)
    )
    if current_user.role == UserRole.buyer:
        q = q.where(ProcurementItem.buyer_id == current_user.id)

    result = await session.execute(q)
    items = result.scalars().all()

    if target_date:
        items = [i for i in items if i.created_at.date() == target_date]

    summary = []
    for item in items:
        cat_name = ""
        if item.category:
            cat_name = item.category.name
        elif item.catalog_item and item.catalog_item.category_id:
            cat_result = await session.get(Category, item.catalog_item.category_id)
            cat_name = cat_result.name if cat_result else "Без категории"

        summary.append(BuyerSummaryItem(
            category_name=cat_name or "Без категории",
            display_name=item.display_name,
            quantity_ordered=float(item.quantity_ordered),
            quantity_received=float(item.quantity_received) if item.quantity_received is not None else None,
            unit=item.unit,
            status=item.status.value,
        ))
    return summary
```

- [ ] **Step 3: Зарегистрировать роутер в `backend/app/main.py`**

Прочитай файл. Добавь:

```python
from app.api.buyer_procurement import router as buyer_procurement_router
# ...
app.include_router(buyer_procurement_router)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/buyer_procurement.py \
        backend/app/api/buyer_procurement.py \
        backend/app/main.py
git commit -m "feat: add /buyer/procurement API (items, update, summary)"
```

---

## Task 4: Buyer Procurement Tests

**Files:**
- Create: `backend/tests/test_buyer_procurement.py`

- [ ] **Step 1: Написать tests — `backend/tests/test_buyer_procurement.py`**

```python
"""Integration tests for /buyer/procurement API."""
from httpx import AsyncClient


async def register(client: AsyncClient, phone: str, role: str, rest_id: str | None = None) -> dict:
    body = {"phone": phone, "password": "pass123", "name": "U", "role": role}
    if rest_id:
        body["restaurant_id"] = rest_id
    resp = await client.post("/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def setup(client: AsyncClient, admin: dict):
    """Returns (buyer_headers, buyer_id, item_id) — item already assigned to buyer."""
    cat = await client.post("/catalog/categories", json={"name": "Мясо", "sort_order": 1}, headers=admin)
    rest = await client.post(
        "/admin/restaurants",
        json={"name": "Р", "address": "A", "contact_phone": "+99673000099"},
        headers=admin,
    )
    rest_id = rest.json()["id"]
    cook = await register(client, "+99673000001", "cook", rest_id)
    buyer_h = await register(client, "+99673000002", "buyer")
    curator = await register(client, "+99673000003", "curator")

    from app.auth.jwt import decode_token
    buyer_id = decode_token(buyer_h["Authorization"].split(" ")[1])["sub"]

    # Create and submit order with raw_name item
    order = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [{"raw_name": "Молоко", "quantity_ordered": "5.0", "unit": "л"}],
        },
        headers=cook,
    )
    order_id = order.json()["id"]
    await client.post(f"/kitchen/orders/{order_id}/submit", headers=cook)

    # Curator assigns item to buyer
    pending = await client.get("/curator/pending", headers=curator)
    item_id = pending.json()[0]["id"]
    await client.post(
        "/curator/assign",
        json={"item_id": item_id, "buyer_id": buyer_id, "save_rule": False},
        headers=curator,
    )
    return buyer_h, buyer_id, item_id


async def test_buyer_sees_assigned_item(client: AsyncClient, admin_token: dict):
    buyer_h, _, item_id = await setup(client, admin_token)
    resp = await client.get("/buyer/procurement/items", headers=buyer_h)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == item_id
    assert items[0]["status"] == "assigned"


async def test_buyer_cannot_see_other_buyers_items(client: AsyncClient, admin_token: dict):
    buyer_h, _, _ = await setup(client, admin_token)
    buyer2 = await register(client, "+99673000020", "buyer")
    resp = await client.get("/buyer/procurement/items", headers=buyer2)
    assert resp.status_code == 200
    assert resp.json() == []  # buyer2 has no assigned items


async def test_cook_cannot_access_buyer_items(client: AsyncClient, admin_token: dict):
    _, _, _ = await setup(client, admin_token)
    rest = await client.post(
        "/admin/restaurants",
        json={"name": "X", "address": "Y", "contact_phone": "+99673000098"},
        headers=admin_token,
    )
    cook = await register(client, "+99673000030", "cook", rest.json()["id"])
    resp = await client.get("/buyer/procurement/items", headers=cook)
    assert resp.status_code == 403


async def test_buyer_updates_quantity_received(client: AsyncClient, admin_token: dict):
    buyer_h, _, item_id = await setup(client, admin_token)
    resp = await client.patch(
        f"/buyer/procurement/items/{item_id}",
        json={"quantity_received": "4.5", "status": "purchased"},
        headers=buyer_h,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["quantity_received"] == 4.5
    assert data["status"] == "purchased"


async def test_buyer_marks_not_found(client: AsyncClient, admin_token: dict):
    buyer_h, _, item_id = await setup(client, admin_token)
    resp = await client.patch(
        f"/buyer/procurement/items/{item_id}",
        json={"status": "not_found"},
        headers=buyer_h,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_found"


async def test_buyer_marks_substituted_with_note(client: AsyncClient, admin_token: dict):
    buyer_h, _, item_id = await setup(client, admin_token)
    resp = await client.patch(
        f"/buyer/procurement/items/{item_id}",
        json={"status": "substituted", "substitution_note": "Взял Простоквашино вместо"},
        headers=buyer_h,
    )
    assert resp.status_code == 200
    assert resp.json()["substitution_note"] == "Взял Простоквашино вместо"


async def test_quantity_ordered_is_immutable(client: AsyncClient, admin_token: dict):
    """Buyer cannot change quantity_ordered — only quantity_received."""
    buyer_h, _, item_id = await setup(client, admin_token)
    # quantity_received is allowed; quantity_ordered is not in the update schema
    resp = await client.patch(
        f"/buyer/procurement/items/{item_id}",
        json={"quantity_received": "3.0"},
        headers=buyer_h,
    )
    item = resp.json()
    assert item["quantity_ordered"] == 5.0  # unchanged
    assert item["quantity_received"] == 3.0


async def test_summary_returns_items(client: AsyncClient, admin_token: dict):
    buyer_h, _, _ = await setup(client, admin_token)
    resp = await client.get("/buyer/procurement/summary", headers=buyer_h)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
```

- [ ] **Step 2: Запустить тесты — ожидать PASS**

```bash
docker compose exec backend pytest tests/test_buyer_procurement.py -v
```

Ожидаемый результат: 9 tests PASS.

- [ ] **Step 3: Запустить все тесты**

```bash
docker compose exec backend pytest tests/ -v
```

Ожидаемый результат: все тесты PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_buyer_procurement.py
git commit -m "test: add buyer procurement API tests"
```

---

## Task 5: Frontend Types Update

**Files:**
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Прочитай `frontend/src/lib/types.ts` и добавь в конец**

```typescript
// Curator

export interface PendingItem {
  id: string
  order_id: string
  display_name: string
  raw_name: string | null
  quantity_ordered: number
  unit: string
  is_catalog_item: boolean
  restaurant_name: string
  created_at: string
}

export interface RoutingRule {
  id: string
  keyword: string
  buyer_id: string
  buyer_name: string
  category_id: string | null
  created_at: string
}

export interface CuratorStats {
  pending_count: number
}

// Buyer Procurement

export interface BuyerItem {
  id: string
  order_id: string
  display_name: string
  raw_name: string | null
  quantity_ordered: number
  quantity_received: number | null
  unit: string
  status: "assigned" | "purchased" | "not_found" | "substituted"
  category_id: string | null
  curator_note: string | null
  substitution_note: string | null
  restaurant_name: string
  created_at: string
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd "/home/danil/Рабочий стол/supplyflow/frontend" && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat: add curator and buyer procurement TypeScript types"
```

---

## Task 6: Frontend — Curator Queue Page

**Files:**
- Create: `frontend/src/app/(curator)/curator/queue/page.tsx`

- [ ] **Step 1: Создать директорию и файл**

Создай файл `frontend/src/app/(curator)/curator/queue/page.tsx`:

```tsx
"use client"

import { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { apiFetch } from "@/lib/api"
import type { PendingItem } from "@/lib/types"

interface BuyerOption {
  id: string
  name: string
}

export default function CuratorQueuePage() {
  const [items, setItems] = useState<PendingItem[]>([])
  const [buyers, setBuyers] = useState<BuyerOption[]>([])
  const [selectedBuyer, setSelectedBuyer] = useState<Record<string, string>>({})
  const [saveRule, setSaveRule] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [pendingData, usersData] = await Promise.all([
        apiFetch<PendingItem[]>("/curator/pending"),
        apiFetch<BuyerOption[]>("/admin/users?role=buyer"),
      ])
      setItems(pendingData)
      setBuyers(usersData)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function handleAssign(itemId: string) {
    const buyerId = selectedBuyer[itemId]
    if (!buyerId) return
    try {
      await apiFetch("/curator/assign", {
        method: "POST",
        body: JSON.stringify({
          item_id: itemId,
          buyer_id: buyerId,
          save_rule: saveRule[itemId] ?? false,
        }),
      })
      setItems((prev) => prev.filter((i) => i.id !== itemId))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка назначения")
    }
  }

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">
        Очередь куратора
        {items.length > 0 && (
          <Badge variant="destructive" className="ml-2">{items.length}</Badge>
        )}
      </h1>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : items.length === 0 ? (
        <p className="text-center text-muted-foreground py-8">Очередь пуста</p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <Card key={item.id}>
              <CardContent className="p-3 space-y-2">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium">{item.display_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.restaurant_name} · {item.quantity_ordered} {item.unit}
                    </p>
                    {!item.is_catalog_item && (
                      <Badge variant="outline" className="text-xs mt-0.5">вручную</Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {new Date(item.created_at).toLocaleDateString("ru-RU")}
                  </p>
                </div>

                <select
                  className="w-full border rounded px-2 py-1 text-sm"
                  value={selectedBuyer[item.id] ?? ""}
                  onChange={(e) =>
                    setSelectedBuyer((prev) => ({ ...prev, [item.id]: e.target.value }))
                  }
                >
                  <option value="">— выберите закупщика —</option>
                  {buyers.map((b) => (
                    <option key={b.id} value={b.id}>{b.name}</option>
                  ))}
                </select>

                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-1 text-sm">
                    <input
                      type="checkbox"
                      checked={saveRule[item.id] ?? false}
                      onChange={(e) =>
                        setSaveRule((prev) => ({ ...prev, [item.id]: e.target.checked }))
                      }
                    />
                    Сохранить как правило
                  </label>
                  <Button
                    size="sm"
                    disabled={!selectedBuyer[item.id]}
                    onClick={() => handleAssign(item.id)}
                  >
                    Назначить
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
```

**Примечание:** Эндпоинт `GET /admin/users?role=buyer` должен существовать. Прочитай `backend/app/api/admin.py` и убедись что есть эндпоинт для получения списка пользователей. Если нет — добавь:

```python
@router.get("/users", response_model=list[UserRead])
async def list_users(
    role: str | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(role_required(UserRole.admin, UserRole.curator)),
):
    q = select(User)
    if role:
        try:
            q = q.where(User.role == UserRole(role))
        except ValueError:
            raise HTTPException(400, detail=f"Invalid role: {role}")
    result = await session.execute(q)
    return result.scalars().all()
```

- [ ] **Step 2: TypeScript check**

```bash
cd "/home/danil/Рабочий стол/supplyflow/frontend" && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(curator)/curator/queue/page.tsx"
git commit -m "feat: add curator queue page"
```

---

## Task 7: Frontend — Curator Rules Page

**Files:**
- Create: `frontend/src/app/(curator)/curator/rules/page.tsx`

- [ ] **Step 1: Создать `frontend/src/app/(curator)/curator/rules/page.tsx`**

```tsx
"use client"

import { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import type { RoutingRule } from "@/lib/types"

interface BuyerOption {
  id: string
  name: string
}

export default function CuratorRulesPage() {
  const [rules, setRules] = useState<RoutingRule[]>([])
  const [buyers, setBuyers] = useState<BuyerOption[]>([])
  const [keyword, setKeyword] = useState("")
  const [buyerId, setBuyerId] = useState("")
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    const [rulesData, usersData] = await Promise.all([
      apiFetch<RoutingRule[]>("/curator/rules"),
      apiFetch<BuyerOption[]>("/admin/users?role=buyer"),
    ])
    setRules(rulesData)
    setBuyers(usersData)
  }, [])

  useEffect(() => { load() }, [load])

  async function handleCreate() {
    if (!keyword.trim() || !buyerId) return
    setCreating(true)
    setError("")
    try {
      const rule = await apiFetch<RoutingRule>("/curator/rules", {
        method: "POST",
        body: JSON.stringify({ keyword: keyword.trim(), buyer_id: buyerId }),
      })
      setRules((prev) => [...prev, rule])
      setKeyword("")
      setBuyerId("")
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка создания")
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(ruleId: string) {
    await apiFetch(`/curator/rules/${ruleId}`, { method: "DELETE" })
    setRules((prev) => prev.filter((r) => r.id !== ruleId))
  }

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">Правила маршрутизации</h1>

      {/* Create rule */}
      <div className="flex gap-2 mb-4">
        <Input
          placeholder="Ключевое слово"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          className="flex-1"
        />
        <select
          className="border rounded px-2 py-1 text-sm"
          value={buyerId}
          onChange={(e) => setBuyerId(e.target.value)}
        >
          <option value="">— закупщик —</option>
          {buyers.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
        <Button onClick={handleCreate} disabled={creating || !keyword.trim() || !buyerId}>
          Добавить
        </Button>
      </div>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {rules.length === 0 ? (
        <p className="text-center text-muted-foreground py-8">Правил пока нет</p>
      ) : (
        <div className="space-y-2">
          {rules.map((rule) => (
            <Card key={rule.id}>
              <CardContent className="p-3 flex items-center justify-between">
                <div>
                  <p className="font-medium font-mono text-sm">«{rule.keyword}»</p>
                  <p className="text-xs text-muted-foreground">→ {rule.buyer_name}</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive"
                  onClick={() => handleDelete(rule.id)}
                >
                  Удалить
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd "/home/danil/Рабочий стол/supplyflow/frontend" && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(curator)/curator/rules/page.tsx"
git commit -m "feat: add curator rules management page"
```

---

## Task 8: Frontend — Buyer Procurement Page

**Files:**
- Create: `frontend/src/app/(buyer)/buyer/procurement/page.tsx`

- [ ] **Step 1: Создать `frontend/src/app/(buyer)/buyer/procurement/page.tsx`**

```tsx
"use client"

import { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import type { BuyerItem } from "@/lib/types"

const STATUS_LABEL: Record<string, string> = {
  assigned: "Назначено",
  purchased: "Куплено",
  not_found: "Не нашёл",
  substituted: "Замена",
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  assigned: "secondary",
  purchased: "default",
  not_found: "destructive",
  substituted: "outline",
}

export default function BuyerProcurementPage() {
  const [items, setItems] = useState<BuyerItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [quantities, setQuantities] = useState<Record<string, string>>({})

  const load = useCallback(() => {
    setLoading(true)
    apiFetch<BuyerItem[]>("/buyer/procurement/items")
      .then((data) => {
        setItems(data)
        const initial: Record<string, string> = {}
        data.forEach((i) => {
          initial[i.id] = i.quantity_received?.toString() ?? ""
        })
        setQuantities(initial)
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  async function updateItem(id: string, patch: { quantity_received?: string; status?: string; substitution_note?: string }) {
    try {
      const body: Record<string, unknown> = {}
      if (patch.status) body.status = patch.status
      if (patch.substitution_note !== undefined) body.substitution_note = patch.substitution_note
      if (patch.quantity_received !== undefined && patch.quantity_received !== "") {
        body.quantity_received = patch.quantity_received
      }
      const updated = await apiFetch<BuyerItem>(`/buyer/procurement/items/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      })
      setItems((prev) => prev.map((i) => (i.id === id ? updated : i)))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка обновления")
    }
  }

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">Мои закупки</h1>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : items.length === 0 ? (
        <p className="text-center text-muted-foreground py-8">Нет назначенных позиций</p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <Card key={item.id}>
              <CardContent className="p-3 space-y-2">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{item.display_name}</p>
                    <p className="text-xs text-muted-foreground">{item.restaurant_name}</p>
                  </div>
                  <Badge variant={STATUS_VARIANT[item.status] ?? "outline"} className="ml-2 shrink-0">
                    {STATUS_LABEL[item.status] ?? item.status}
                  </Badge>
                </div>

                {/* Ordered vs Received */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-xs text-muted-foreground mb-0.5">Заказано</p>
                    <p className="text-sm font-medium">
                      {item.quantity_ordered} {item.unit}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-0.5">Получено</p>
                    <div className="flex gap-1">
                      <Input
                        type="number"
                        min="0"
                        step="0.001"
                        value={quantities[item.id] ?? ""}
                        onChange={(e) =>
                          setQuantities((prev) => ({ ...prev, [item.id]: e.target.value }))
                        }
                        onBlur={() => {
                          if (quantities[item.id] !== (item.quantity_received?.toString() ?? "")) {
                            updateItem(item.id, { quantity_received: quantities[item.id] })
                          }
                        }}
                        className="h-7 text-sm"
                      />
                      <span className="text-sm self-center">{item.unit}</span>
                    </div>
                  </div>
                </div>

                {/* Status buttons */}
                {item.status === "assigned" && (
                  <div className="flex gap-1 flex-wrap">
                    <Button
                      size="sm"
                      variant="default"
                      onClick={() => updateItem(item.id, { status: "purchased" })}
                    >
                      Куплено
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => updateItem(item.id, { status: "not_found" })}
                    >
                      Не нашёл
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        const note = prompt("Чем заменили?")
                        if (note) updateItem(item.id, { status: "substituted", substitution_note: note })
                      }}
                    >
                      Замена
                    </Button>
                  </div>
                )}

                {item.substitution_note && (
                  <p className="text-xs text-muted-foreground">
                    Замена: {item.substitution_note}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd "/home/danil/Рабочий стол/supplyflow/frontend" && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(buyer)/buyer/procurement/page.tsx"
git commit -m "feat: add buyer procurement page (assigned items, quantity input, status buttons)"
```

---

## Task 9: Final Verification

- [ ] **Step 1: Запустить все backend тесты**

```bash
docker compose exec backend pytest tests/ -v
```

Ожидаемый результат: все тесты PASS.

- [ ] **Step 2: TypeScript check**

```bash
cd "/home/danil/Рабочий стол/supplyflow/frontend" && npx tsc --noEmit
```

- [ ] **Step 3: Проверить новые эндпоинты**

```bash
# Должны вернуть 401, не 404
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/curator/pending
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/buyer/procurement/items
```

- [ ] **Step 4: Финальный commit**

```bash
git add -A
git commit -m "feat: procurement P2 complete — curator queue/rules, buyer procurement items UI"
```
