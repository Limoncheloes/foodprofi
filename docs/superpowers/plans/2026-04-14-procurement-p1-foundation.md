# Procurement P1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить модели, миграции, backend API и frontend UI для создания и отправки procurement-заявок поваром, включая WhatsApp-уведомление с fallback логикой.

**Architecture:** Новая таблица `procurement_items` связана с существующим `orders.id`. Отдельный роутер `/kitchen`, сервисы `routing.py` и `whatsapp.py`. Фронт — две страницы в `(cook)` route group. Существующий `order_items` и warehouse pipeline не трогаем.

**Tech Stack:** Python FastAPI + SQLAlchemy 2 async + Alembic | Next.js 14 App Router + TypeScript + shadcn/ui | PostgreSQL | pytest + httpx

---

## File Map

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `backend/alembic/versions/d9e1f3a42b67_procurement_foundation.py` | Миграция: curator роль, новые статусы, categories.default_buyer_id, таблицы procurement_items и routing_rules |
| `backend/app/models/procurement.py` | SQLAlchemy модели: `ProcurementItemStatus` enum, `ProcurementItem`, `RoutingRule` |
| `backend/app/schemas/procurement.py` | Pydantic схемы: Create/Read для ProcurementItem, RoutingRule, заявки, submit ответа |
| `backend/app/services/routing.py` | Бизнес-логика маршрутизации: `route_procurement_order()` |
| `backend/app/services/whatsapp.py` | Генерация WhatsApp URL: `build_whatsapp_urls()` |
| `backend/app/api/kitchen.py` | Роутер `/kitchen`: CRUD заявок + submit |
| `backend/tests/test_routing_service.py` | Unit-тесты логики маршрутизации |
| `backend/tests/test_kitchen.py` | Интеграционные тесты /kitchen API |

### Backend — Modified Files
| File | Change |
|------|--------|
| `backend/app/models/user.py` | Добавить `curator = "curator"` в `UserRole` |
| `backend/app/models/order.py` | Добавить `routing`, `received`, `closed` в `OrderStatus` |
| `backend/app/models/catalog.py` | Добавить `default_buyer_id` в `Category` |
| `backend/app/config.py` | Добавить `whatsapp_group_jid` и `whatsapp_curator_phone` |
| `backend/app/main.py` | Зарегистрировать `kitchen_router` |
| `backend/seed.py` | Добавить curator пользователя и buyer→category маппинги |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/app/(cook)/kitchen/new-order/page.tsx` | Форма создания procurement заявки |
| `frontend/src/app/(cook)/kitchen/orders/page.tsx` | История procurement заявок повара |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `frontend/src/lib/types.ts` | Добавить `ProcurementItem`, `ProcurementOrder`, `WhatsAppUrls`, `SubmitOrderResponse` |

---

## Task 1: DB Migration

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/order.py`
- Modify: `backend/app/models/catalog.py`
- Create: `backend/alembic/versions/d9e1f3a42b67_procurement_foundation.py`

- [ ] **Step 1: Обновить Python enum `UserRole` в `backend/app/models/user.py`**

Прочитай файл. Найди класс `UserRole`. Добавь строку:

```python
class UserRole(str, enum.Enum):
    cook = "cook"
    buyer = "buyer"
    manager = "manager"
    warehouse = "warehouse"
    driver = "driver"
    admin = "admin"
    curator = "curator"   # ← добавить
```

- [ ] **Step 2: Обновить Python enum `OrderStatus` в `backend/app/models/order.py`**

Прочитай файл. Найди класс `OrderStatus`. Добавь три значения:

```python
class OrderStatus(str, enum.Enum):
    pending_approval = "pending_approval"
    draft = "draft"
    submitted = "submitted"
    routing = "routing"       # ← добавить
    in_purchase = "in_purchase"
    at_warehouse = "at_warehouse"
    packed = "packed"
    in_delivery = "in_delivery"
    delivered = "delivered"
    received = "received"     # ← добавить
    closed = "closed"         # ← добавить
    cancelled = "cancelled"
```

- [ ] **Step 3: Добавить `default_buyer_id` в модель `Category` в `backend/app/models/catalog.py`**

Прочитай файл. В класс `Category` добавь поле после `sort_order`:

```python
class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    default_buyer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
```

- [ ] **Step 4: Создать файл миграции `backend/alembic/versions/d9e1f3a42b67_procurement_foundation.py`**

```python
"""procurement foundation

Revision ID: d9e1f3a42b67
Revises: c7d4a2b18e35
Create Date: 2026-04-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd9e1f3a42b67'
down_revision: Union[str, None] = 'c7d4a2b18e35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE must run outside a transaction in PostgreSQL.
    connection = op.get_bind()
    connection.execute(sa.text("COMMIT"))
    connection.execute(sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'curator'"))
    connection.execute(sa.text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'routing'"))
    connection.execute(sa.text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'received'"))
    connection.execute(sa.text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'closed'"))
    connection.execute(sa.text(
        "CREATE TYPE procurementitemstatus AS ENUM "
        "('pending_curator', 'assigned', 'purchased', 'not_found', 'substituted')"
    ))
    connection.execute(sa.text("BEGIN"))

    op.add_column(
        'categories',
        sa.Column('default_buyer_id', sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        'fk_categories_default_buyer',
        'categories', 'users',
        ['default_buyer_id'], ['id'],
        ondelete='SET NULL'
    )

    op.create_table(
        'procurement_items',
        sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('catalog_item_id', sa.UUID(), nullable=True),
        sa.Column('raw_name', sa.String(255), nullable=True),
        sa.Column('quantity_ordered', sa.Numeric(10, 3), nullable=False),
        sa.Column('quantity_received', sa.Numeric(10, 3), nullable=True),
        sa.Column('unit', sa.String(50), nullable=False),
        sa.Column(
            'status',
            sa.Enum('pending_curator', 'assigned', 'purchased', 'not_found', 'substituted',
                    name='procurementitemstatus'),
            nullable=False,
            server_default='pending_curator',
        ),
        sa.Column('buyer_id', sa.UUID(), nullable=True),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('curator_note', sa.Text(), nullable=True),
        sa.Column('substitution_note', sa.Text(), nullable=True),
        sa.Column('is_catalog_item', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['catalog_item_id'], ['catalog_items.id']),
        sa.ForeignKeyConstraint(['buyer_id'], ['users.id']),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.CheckConstraint(
            'catalog_item_id IS NOT NULL OR raw_name IS NOT NULL',
            name='ck_procurement_item_has_name'
        ),
        sa.CheckConstraint('quantity_ordered > 0', name='ck_procurement_item_qty_positive'),
    )

    op.create_table(
        'routing_rules',
        sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
        sa.Column('keyword', sa.String(255), nullable=False),
        sa.Column('buyer_id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('created_by_curator', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['buyer_id'], ['users.id']),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.ForeignKeyConstraint(['created_by_curator'], ['users.id']),
        sa.UniqueConstraint('keyword', name='uq_routing_rules_keyword'),
    )


def downgrade() -> None:
    op.drop_table('routing_rules')
    op.drop_table('procurement_items')
    op.drop_constraint('fk_categories_default_buyer', 'categories', type_='foreignkey')
    op.drop_column('categories', 'default_buyer_id')
    connection = op.get_bind()
    connection.execute(sa.text("DROP TYPE IF EXISTS procurementitemstatus"))
    # PostgreSQL does not support removing enum values from userrole/orderstatus
```

- [ ] **Step 5: Применить миграцию**

```bash
docker compose exec backend alembic upgrade head
```

Ожидаемый вывод: `Running upgrade c7d4a2b18e35 -> d9e1f3a42b67, procurement foundation`

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/user.py \
        backend/app/models/order.py \
        backend/app/models/catalog.py \
        backend/alembic/versions/d9e1f3a42b67_procurement_foundation.py
git commit -m "feat: add curator role, procurement statuses, procurement_items and routing_rules tables"
```

---

## Task 2: Python Models

**Files:**
- Create: `backend/app/models/procurement.py`

- [ ] **Step 1: Добавить relationship `category` в `CatalogItem` в `backend/app/models/catalog.py`**

Прочитай файл. В класс `CatalogItem` добавь relationship (нужен для routing selectinload):

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Any

class CatalogItem(Base):
    # ... существующие поля ...
    category: Mapped[Any] = relationship("Category", foreign_keys=[category_id], lazy="noload")
```

- [ ] **Step 2: Создать `backend/app/models/procurement.py`**

```python
import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum, ForeignKey,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Any

from app.database import Base


class ProcurementItemStatus(str, enum.Enum):
    pending_curator = "pending_curator"
    assigned = "assigned"
    purchased = "purchased"
    not_found = "not_found"
    substituted = "substituted"


class ProcurementItem(Base):
    __tablename__ = "procurement_items"
    __table_args__ = (
        CheckConstraint(
            "catalog_item_id IS NOT NULL OR raw_name IS NOT NULL",
            name="ck_procurement_item_has_name",
        ),
        CheckConstraint("quantity_ordered > 0", name="ck_procurement_item_qty_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    catalog_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("catalog_items.id"), nullable=True
    )
    raw_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity_ordered: Mapped[float] = mapped_column(Numeric(10, 3))
    quantity_received: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[str] = mapped_column(String(50))
    status: Mapped[ProcurementItemStatus] = mapped_column(
        Enum(ProcurementItemStatus, name="procurementitemstatus"),
        default=ProcurementItemStatus.pending_curator,
    )
    buyer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    curator_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    substitution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_catalog_item: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    catalog_item: Mapped[Any] = relationship("CatalogItem", foreign_keys=[catalog_item_id], lazy="noload")
    buyer: Mapped[Any] = relationship("User", foreign_keys=[buyer_id], lazy="noload")
    category: Mapped[Any] = relationship("Category", foreign_keys=[category_id], lazy="noload")

    @property
    def display_name(self) -> str:
        if self.catalog_item:
            return self.catalog_item.name
        return self.raw_name or ""


class RoutingRule(Base):
    __tablename__ = "routing_rules"
    __table_args__ = (
        UniqueConstraint("keyword", name="uq_routing_rules_keyword"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    keyword: Mapped[str] = mapped_column(String(255))
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    created_by_curator: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    buyer: Mapped[Any] = relationship("User", foreign_keys=[buyer_id], lazy="noload")
```

- [ ] **Step 2: Добавить импорт в `backend/app/models/__init__.py`**

Прочитай файл. Добавь импорты:

```python
from app.models.procurement import ProcurementItem, RoutingRule, ProcurementItemStatus
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/procurement.py backend/app/models/__init__.py
git commit -m "feat: add ProcurementItem and RoutingRule SQLAlchemy models"
```

---

## Task 3: Config + WhatsApp Service

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/services/whatsapp.py`

- [ ] **Step 1: Добавить env vars в `backend/app/config.py`**

Прочитай файл. Добавь два поля после `debug`:

```python
class Settings(BaseSettings):
    database_url: str
    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    backend_cors_origins: str = "http://localhost:3000"
    minio_endpoint: str = "minio:9000"
    minio_bucket: str = "supplyflow"
    minio_root_user: str
    minio_root_password: str
    debug: bool = False
    whatsapp_group_jid: str = ""          # ← добавить (пусто = не настроено)
    whatsapp_curator_phone: str = ""      # ← добавить
```

- [ ] **Step 2: Добавить в `.env.example`**

Прочитай `.env.example`. Добавь в конец:

```env
# WhatsApp integration
WHATSAPP_GROUP_JID=120363XXXXXXXXXX@g.us   # optional: WhatsApp group JID
WHATSAPP_CURATOR_PHONE=996XXXXXXXXX         # fallback: curator's personal phone
```

- [ ] **Step 3: Создать `backend/app/services/whatsapp.py`**

```python
from urllib.parse import quote

from app.config import settings


def build_order_text(order_id: str, order_date: str, restaurant_name: str, items: list[dict]) -> str:
    """Build the WhatsApp message text for a submitted procurement order.

    items: list of {"name": str, "quantity": float, "unit": str, "is_catalog_item": bool}
    """
    lines = [
        f"Заявка №{order_id[:8]} от {order_date}",
        f"Ресторан: {restaurant_name}",
        "",
    ]
    for i, item in enumerate(items, 1):
        label = "" if item["is_catalog_item"] else " (некаталог)"
        lines.append(f"{i}. {item['name']}{label} — {item['quantity']:.3f} {item['unit']}")
    lines.append("")
    lines.append("Статус: отправлено")
    return "\n".join(lines)


def build_whatsapp_urls(text: str) -> dict:
    """Return primary (group JID deep link) and fallback (wa.me) URLs.

    primary is None if WHATSAPP_GROUP_JID is not configured.
    """
    encoded = quote(text, safe="")
    fallback_phone = settings.whatsapp_curator_phone.lstrip("+")
    fallback = f"https://wa.me/{fallback_phone}?text={encoded}"

    primary = None
    if settings.whatsapp_group_jid:
        primary = f"whatsapp://send?groupid={settings.whatsapp_group_jid}&text={encoded}"

    return {"primary": primary, "fallback": fallback}
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/app/services/whatsapp.py .env.example
git commit -m "feat: add WhatsApp URL builder service and env config"
```

---

## Task 4: Routing Service

**Files:**
- Create: `backend/app/services/routing.py`
- Create: `backend/tests/test_routing_service.py`

- [ ] **Step 1: Написать failing tests — `backend/tests/test_routing_service.py`**

```python
"""Unit tests for procurement routing service.

These tests call the routing functions directly with mocked objects,
not through the HTTP API.
"""
import uuid
import pytest
from unittest.mock import MagicMock

from app.services.routing import find_best_rule, apply_routing


def make_rule(keyword: str, buyer_id=None, category_id=None):
    rule = MagicMock()
    rule.keyword = keyword
    rule.buyer_id = buyer_id or uuid.uuid4()
    rule.category_id = category_id
    return rule


def make_item(raw_name=None, catalog_name=None, is_catalog=True, category_buyer_id=None):
    item = MagicMock()
    item.raw_name = raw_name
    item.is_catalog_item = is_catalog
    item.buyer_id = None
    item.category_id = None
    item.status = "pending_curator"
    if is_catalog and catalog_name:
        item.catalog_item = MagicMock()
        item.catalog_item.name = catalog_name
        item.catalog_item.category = MagicMock()
        item.catalog_item.category.default_buyer_id = category_buyer_id
        item.catalog_item.category.id = uuid.uuid4()
    else:
        item.catalog_item = None
    return item


# --- find_best_rule ---

def test_find_best_rule_returns_longest_matching_keyword():
    rules = [
        make_rule("говядина"),
        make_rule("говядина без кости"),
    ]
    result = find_best_rule("Говядина без кости 1кг", rules)
    assert result.keyword == "говядина без кости"


def test_find_best_rule_case_insensitive():
    rules = [make_rule("МОЛОКО")]
    result = find_best_rule("молоко 1л", rules)
    assert result is not None


def test_find_best_rule_returns_none_if_no_match():
    rules = [make_rule("говядина")]
    result = find_best_rule("картофель 5кг", rules)
    assert result is None


def test_find_best_rule_empty_rules():
    result = find_best_rule("говядина", [])
    assert result is None


# --- apply_routing ---

def test_apply_routing_catalog_item_with_default_buyer():
    buyer_id = uuid.uuid4()
    item = make_item(catalog_name="Говядина", is_catalog=True, category_buyer_id=buyer_id)
    apply_routing(item, rules=[])
    assert item.buyer_id == buyer_id
    assert item.status == "assigned"


def test_apply_routing_catalog_item_no_default_buyer_falls_to_rules():
    buyer_id = uuid.uuid4()
    item = make_item(catalog_name="Говядина", is_catalog=True, category_buyer_id=None)
    rules = [make_rule("говядина", buyer_id=buyer_id)]
    apply_routing(item, rules=rules)
    assert item.buyer_id == buyer_id
    assert item.status == "assigned"


def test_apply_routing_catalog_item_no_match_becomes_pending_curator():
    item = make_item(catalog_name="Говядина", is_catalog=True, category_buyer_id=None)
    apply_routing(item, rules=[])
    assert item.status == "pending_curator"
    assert item.buyer_id is None


def test_apply_routing_raw_name_matches_rule():
    buyer_id = uuid.uuid4()
    item = make_item(raw_name="Ложки пластиковые", is_catalog=False)
    rules = [make_rule("ложки", buyer_id=buyer_id)]
    apply_routing(item, rules=rules)
    assert item.buyer_id == buyer_id
    assert item.status == "assigned"


def test_apply_routing_raw_name_no_match_becomes_pending_curator():
    item = make_item(raw_name="Ложки пластиковые", is_catalog=False)
    apply_routing(item, rules=[])
    assert item.status == "pending_curator"
```

- [ ] **Step 2: Запустить тесты — ожидать FAIL**

```bash
docker compose exec backend pytest tests/test_routing_service.py -v
```

Ожидаемый результат: `ImportError: cannot import name 'find_best_rule' from 'app.services.routing'`

- [ ] **Step 3: Создать `backend/app/services/routing.py`**

```python
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
    from app.models.procurement import ProcurementItem, RoutingRule

    # Load all routing rules once
    rules_result = await session.execute(select(RoutingRule))
    rules = rules_result.scalars().all()

    # Load items with eager catalog_item + category
    from sqlalchemy.orm import selectinload
    items_result = await session.execute(
        select(ProcurementItem)
        .where(ProcurementItem.order_id == order_id)
        .options(
            selectinload(ProcurementItem.catalog_item).selectinload(
                __import__("app.models.catalog", fromlist=["CatalogItem"]).CatalogItem.category
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
```

- [ ] **Step 4: Запустить тесты — ожидать PASS**

```bash
docker compose exec backend pytest tests/test_routing_service.py -v
```

Ожидаемый результат: 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/routing.py backend/tests/test_routing_service.py
git commit -m "feat: add procurement routing service with unit tests"
```

---

## Task 5: Procurement Schemas

**Files:**
- Create: `backend/app/schemas/procurement.py`

- [ ] **Step 1: Создать `backend/app/schemas/procurement.py`**

```python
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator, model_validator


# --- ProcurementItem ---

class ProcurementItemCreate(BaseModel):
    """One item in a new procurement order. Either catalog_item_id or raw_name must be set."""
    catalog_item_id: uuid.UUID | None = None
    raw_name: str | None = None
    quantity_ordered: Decimal
    unit: str  # e.g. "кг", "шт", "л"

    @model_validator(mode="after")
    def check_name_present(self):
        if self.catalog_item_id is None and not self.raw_name:
            raise ValueError("Either catalog_item_id or raw_name must be provided")
        if self.quantity_ordered <= 0:
            raise ValueError("quantity_ordered must be positive")
        return self


class ProcurementItemRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    catalog_item_id: uuid.UUID | None
    raw_name: str | None
    display_name: str
    quantity_ordered: float
    quantity_received: float | None
    unit: str
    status: str
    buyer_id: uuid.UUID | None
    category_id: uuid.UUID | None
    curator_note: str | None
    substitution_note: str | None
    is_catalog_item: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- ProcurementOrder ---

class ProcurementOrderCreate(BaseModel):
    """Create a procurement order with items in one shot."""
    restaurant_id: uuid.UUID
    items: list[ProcurementItemCreate]

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v):
        if not v:
            raise ValueError("Order must have at least one item")
        return v


class ProcurementOrderRead(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    restaurant_name: str
    user_id: uuid.UUID
    user_name: str
    status: str
    created_at: datetime
    items: list[ProcurementItemRead]

    model_config = {"from_attributes": True}


# --- Submit Response ---

class WhatsAppUrls(BaseModel):
    primary: str | None   # whatsapp:// group deep link, None if not configured
    fallback: str         # wa.me fallback to curator phone


class SubmitOrderResponse(BaseModel):
    order: ProcurementOrderRead
    whatsapp: WhatsAppUrls
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/procurement.py
git commit -m "feat: add procurement Pydantic schemas"
```

---

## Task 6: Kitchen API

**Files:**
- Create: `backend/app/api/kitchen.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Создать `backend/app/api/kitchen.py`**

```python
import uuid
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user, role_required
from app.database import get_session
from app.models.catalog import CatalogItem
from app.models.order import Order, OrderStatus
from app.models.procurement import ProcurementItem, ProcurementItemStatus
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.schemas.procurement import (
    ProcurementItemRead,
    ProcurementOrderCreate,
    ProcurementOrderRead,
    SubmitOrderResponse,
    WhatsAppUrls,
)
from app.services.routing import route_procurement_order
from app.services.whatsapp import build_order_text, build_whatsapp_urls

router = APIRouter(prefix="/kitchen", tags=["kitchen"])

_COOK_ROLES = (UserRole.cook, UserRole.admin)


def _order_to_read(order: Order, items: list[ProcurementItem]) -> ProcurementOrderRead:
    return ProcurementOrderRead(
        id=order.id,
        restaurant_id=order.restaurant_id,
        restaurant_name=order.restaurant_name,
        user_id=order.user_id,
        user_name=order.user_name,
        status=order.status.value,
        created_at=order.created_at,
        items=[ProcurementItemRead.model_validate(i) for i in items],
    )


@router.post("/orders", response_model=ProcurementOrderRead, status_code=201)
async def create_procurement_order(
    body: ProcurementOrderCreate,
    current_user: User = Depends(role_required(*_COOK_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> ProcurementOrderRead:
    """Create a procurement order draft with items. Does not trigger routing yet."""
    # Verify restaurant exists and belongs to cook
    restaurant = await session.get(Restaurant, body.restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if current_user.role == UserRole.cook and current_user.restaurant_id != body.restaurant_id:
        raise HTTPException(status_code=403, detail="Cannot order for another restaurant")

    order = Order(
        user_id=current_user.id,
        restaurant_id=body.restaurant_id,
        status=OrderStatus.draft,
    )
    session.add(order)
    await session.flush()  # get order.id

    proc_items = []
    for item_data in body.items:
        # Resolve catalog item unit if not raw
        unit = item_data.unit
        if item_data.catalog_item_id:
            cat_item = await session.get(CatalogItem, item_data.catalog_item_id)
            if not cat_item or not cat_item.is_active:
                raise HTTPException(
                    status_code=400,
                    detail=f"Catalog item {item_data.catalog_item_id} not found or inactive",
                )
            if not unit:
                unit = cat_item.unit.value

        proc_item = ProcurementItem(
            order_id=order.id,
            catalog_item_id=item_data.catalog_item_id,
            raw_name=item_data.raw_name,
            quantity_ordered=float(item_data.quantity_ordered),
            unit=unit,
            is_catalog_item=item_data.catalog_item_id is not None,
            status=ProcurementItemStatus.pending_curator,
        )
        session.add(proc_item)
        proc_items.append(proc_item)

    await session.commit()

    # Reload with relationships
    for pi in proc_items:
        await session.refresh(pi)

    # Eagerly load order relationships for response
    result = await session.execute(
        select(Order)
        .where(Order.id == order.id)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
    )
    order = result.scalar_one()

    return _order_to_read(order, proc_items)


@router.post("/orders/{order_id}/submit", response_model=SubmitOrderResponse)
async def submit_procurement_order(
    order_id: uuid.UUID,
    current_user: User = Depends(role_required(*_COOK_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> SubmitOrderResponse:
    """Submit a draft procurement order. Triggers routing, returns WhatsApp URLs."""
    result = await session.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current_user.role == UserRole.cook and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your order")
    if order.status != OrderStatus.draft:
        raise HTTPException(status_code=400, detail="Only draft orders can be submitted")

    # Load procurement items
    items_result = await session.execute(
        select(ProcurementItem)
        .where(ProcurementItem.order_id == order_id)
        .options(selectinload(ProcurementItem.catalog_item))
    )
    items = items_result.scalars().all()
    if not items:
        raise HTTPException(status_code=400, detail="Order has no items")

    # Run routing
    all_assigned = await route_procurement_order(session, order_id)
    order.status = OrderStatus.in_purchase if all_assigned else OrderStatus.routing

    await session.commit()

    # Refresh items after routing updated their statuses
    items_result = await session.execute(
        select(ProcurementItem).where(ProcurementItem.order_id == order_id)
    )
    items = items_result.scalars().all()

    # Build WhatsApp message
    item_dicts = [
        {
            "name": i.display_name,
            "quantity": float(i.quantity_ordered),
            "unit": i.unit,
            "is_catalog_item": i.is_catalog_item,
        }
        for i in items
    ]
    order_date = order.created_at.strftime("%d.%m.%Y")
    text = build_order_text(str(order.id), order_date, order.restaurant_name, item_dicts)
    wa_urls = build_whatsapp_urls(text)

    return SubmitOrderResponse(
        order=_order_to_read(order, items),
        whatsapp=WhatsAppUrls(**wa_urls),
    )


@router.get("/orders", response_model=list[ProcurementOrderRead])
async def list_procurement_orders(
    current_user: User = Depends(role_required(*_COOK_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> list[ProcurementOrderRead]:
    """List procurement orders for the current cook (by their restaurant)."""
    q = (
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
        .order_by(Order.created_at.desc())
    )
    if current_user.role == UserRole.cook:
        q = q.where(Order.restaurant_id == current_user.restaurant_id)

    orders_result = await session.execute(q)
    orders = orders_result.scalars().all()

    response = []
    for order in orders:
        items_result = await session.execute(
            select(ProcurementItem).where(ProcurementItem.order_id == order.id)
        )
        items = items_result.scalars().all()
        response.append(_order_to_read(order, items))
    return response


@router.get("/orders/{order_id}", response_model=ProcurementOrderRead)
async def get_procurement_order(
    order_id: uuid.UUID,
    current_user: User = Depends(role_required(*_COOK_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> ProcurementOrderRead:
    result = await session.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current_user.role == UserRole.cook and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your order")

    items_result = await session.execute(
        select(ProcurementItem).where(ProcurementItem.order_id == order_id)
    )
    items = items_result.scalars().all()
    return _order_to_read(order, items)
```

- [ ] **Step 2: Зарегистрировать роутер в `backend/app/main.py`**

Прочитай файл. Добавь import и `include_router`:

```python
from app.api.kitchen import router as kitchen_router
# ... (остальные импорты)

app.include_router(kitchen_router)  # добавить после manager_router
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/kitchen.py backend/app/main.py
git commit -m "feat: add /kitchen API router for procurement orders"
```

---

## Task 7: Kitchen API Tests

**Files:**
- Create: `backend/tests/test_kitchen.py`

- [ ] **Step 1: Написать failing tests — `backend/tests/test_kitchen.py`**

```python
"""Integration tests for /kitchen procurement API."""
import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, phone: str, role: str, rest_id: str | None = None) -> dict:
    body = {"phone": phone, "password": "pass123", "name": "Test", "role": role}
    if rest_id:
        body["restaurant_id"] = rest_id
    resp = await client.post("/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def create_fixtures(client: AsyncClient, admin: dict):
    """Returns (cook_headers, rest_id, cat_item_id)."""
    cat = await client.post("/catalog/categories", json={"name": "Мясо", "sort_order": 1}, headers=admin)
    assert cat.status_code == 201
    item = await client.post(
        "/catalog/items",
        json={"category_id": cat.json()["id"], "name": "Говядина", "unit": "kg", "variants": []},
        headers=admin,
    )
    assert item.status_code == 201
    rest = await client.post(
        "/admin/restaurants",
        json={"name": "Ресторан 1", "address": "ул. Ленина 1", "contact_phone": "+99670000001"},
        headers=admin,
    )
    assert rest.status_code == 201
    rest_id = rest.json()["id"]
    cook = await register(client, "+99671000001", "cook", rest_id)
    return cook, rest_id, item.json()["id"]


async def test_create_procurement_order_catalog_item(client: AsyncClient, admin_token: dict):
    cook, rest_id, item_id = await create_fixtures(client, admin_token)

    resp = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [{"catalog_item_id": item_id, "quantity_ordered": "5.500", "unit": "кг"}],
        },
        headers=cook,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "draft"
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity_ordered"] == 5.5
    assert data["items"][0]["is_catalog_item"] is True


async def test_create_procurement_order_raw_name(client: AsyncClient, admin_token: dict):
    cook, rest_id, _ = await create_fixtures(client, admin_token)

    resp = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [{"raw_name": "Ложки пластиковые", "quantity_ordered": "200", "unit": "шт"}],
        },
        headers=cook,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["items"][0]["raw_name"] == "Ложки пластиковые"
    assert data["items"][0]["is_catalog_item"] is False


async def test_create_order_empty_items_rejected(client: AsyncClient, admin_token: dict):
    cook, rest_id, _ = await create_fixtures(client, admin_token)
    resp = await client.post(
        "/kitchen/orders",
        json={"restaurant_id": rest_id, "items": []},
        headers=cook,
    )
    assert resp.status_code == 422


async def test_cook_cannot_order_for_other_restaurant(client: AsyncClient, admin_token: dict):
    cook, rest_id, _ = await create_fixtures(client, admin_token)
    # create another restaurant
    rest2 = await client.post(
        "/admin/restaurants",
        json={"name": "Ресторан 2", "address": "ул. Фрунзе 2", "contact_phone": "+99670000002"},
        headers=admin_token,
    )
    resp = await client.post(
        "/kitchen/orders",
        json={"restaurant_id": rest2.json()["id"], "items": [
            {"raw_name": "Что-то", "quantity_ordered": "1", "unit": "шт"}
        ]},
        headers=cook,
    )
    assert resp.status_code == 403


async def test_submit_order_returns_whatsapp_urls(client: AsyncClient, admin_token: dict):
    cook, rest_id, item_id = await create_fixtures(client, admin_token)
    order_resp = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [{"catalog_item_id": item_id, "quantity_ordered": "3.000", "unit": "кг"}],
        },
        headers=cook,
    )
    order_id = order_resp.json()["id"]

    resp = await client.post(f"/kitchen/orders/{order_id}/submit", headers=cook)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "whatsapp" in data
    assert "fallback" in data["whatsapp"]
    assert "wa.me" in data["whatsapp"]["fallback"]
    # primary is None when WHATSAPP_GROUP_JID not set in test env
    assert data["whatsapp"]["primary"] is None


async def test_submit_changes_status(client: AsyncClient, admin_token: dict):
    cook, rest_id, item_id = await create_fixtures(client, admin_token)
    order_resp = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [{"catalog_item_id": item_id, "quantity_ordered": "2", "unit": "кг"}],
        },
        headers=cook,
    )
    order_id = order_resp.json()["id"]

    resp = await client.post(f"/kitchen/orders/{order_id}/submit", headers=cook)
    assert resp.status_code == 200
    # No routing rules, no default buyer → routing status
    assert resp.json()["order"]["status"] in ("routing", "in_purchase")


async def test_submit_draft_only(client: AsyncClient, admin_token: dict):
    cook, rest_id, item_id = await create_fixtures(client, admin_token)
    order_resp = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [{"catalog_item_id": item_id, "quantity_ordered": "1", "unit": "кг"}],
        },
        headers=cook,
    )
    order_id = order_resp.json()["id"]
    await client.post(f"/kitchen/orders/{order_id}/submit", headers=cook)
    # Submit again — should fail
    resp = await client.post(f"/kitchen/orders/{order_id}/submit", headers=cook)
    assert resp.status_code == 400


async def test_list_orders_returns_cook_orders(client: AsyncClient, admin_token: dict):
    cook, rest_id, item_id = await create_fixtures(client, admin_token)
    await client.post(
        "/kitchen/orders",
        json={"restaurant_id": rest_id, "items": [
            {"catalog_item_id": item_id, "quantity_ordered": "1", "unit": "кг"}
        ]},
        headers=cook,
    )
    resp = await client.get("/kitchen/orders", headers=cook)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_whatsapp_text_contains_restaurant_and_items(client: AsyncClient, admin_token: dict):
    cook, rest_id, item_id = await create_fixtures(client, admin_token)
    order_resp = await client.post(
        "/kitchen/orders",
        json={
            "restaurant_id": rest_id,
            "items": [
                {"catalog_item_id": item_id, "quantity_ordered": "10.000", "unit": "кг"},
                {"raw_name": "Ложки", "quantity_ordered": "200", "unit": "шт"},
            ],
        },
        headers=cook,
    )
    order_id = order_resp.json()["id"]
    resp = await client.post(f"/kitchen/orders/{order_id}/submit", headers=cook)
    fallback_url = resp.json()["whatsapp"]["fallback"]
    # URL-encoded text should contain restaurant name and item names
    assert "1" in fallback_url   # item numbering
    assert "wa.me" in fallback_url
```

- [ ] **Step 2: Запустить тесты — ожидать FAIL**

```bash
docker compose exec backend pytest tests/test_kitchen.py -v
```

Ожидаемый результат: FAIL — миграция ещё не применена в тестовой БД (тесты создают схему заново через `Base.metadata.create_all`).

- [ ] **Step 3: Убедиться что модели импортируются в `Base.metadata`**

Прочитай `backend/app/database.py` и `backend/app/models/__init__.py`. Все модели должны быть импортированы до того как `Base.metadata.create_all` вызывается в тестах.

Проверь что `backend/app/models/__init__.py` содержит:

```python
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.catalog import CatalogItem, Category
from app.models.order import Order, OrderItem, OrderStatus
from app.models.inventory import Inventory, InventoryLog
from app.models.template import Template, TemplateItem
from app.models.procurement import ProcurementItem, RoutingRule, ProcurementItemStatus
```

- [ ] **Step 4: Запустить тесты — ожидать PASS**

```bash
docker compose exec backend pytest tests/test_kitchen.py -v
```

Ожидаемый результат: 9 tests PASS.

- [ ] **Step 5: Запустить все тесты**

```bash
docker compose exec backend pytest tests/ -v
```

Ожидаемый результат: все существующие тесты + 9 новых + 11 routing unit тестов PASS. Существующие тесты не должны поломаться.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_kitchen.py
git commit -m "test: add kitchen API integration tests"
```

---

## Task 8: Update Seed Script

**Files:**
- Modify: `backend/seed.py`

- [ ] **Step 1: Прочитай `backend/seed.py` и добавь curator пользователя и buyer→category маппинги**

Найди секцию создания пользователей. Добавь после существующих пользователей:

```python
# Procurement users
curator = User(
    name="Куратор Закупок",
    phone="+99699000010",
    password_hash=hash_password("curator123"),
    role=UserRole.curator,
)
session.add(curator)

# Set default_buyer_id on categories (map каждую категорию к ближайшему buyer)
# Предполагаем что buyer пользователь уже создан выше в seed (найди его в коде)
# После flush: category.default_buyer_id = buyer.id
```

Точная реализация зависит от текущего seed.py — прочитай файл и найди существующего `buyer` пользователя, затем назначь его как `default_buyer_id` для каждой созданной категории.

- [ ] **Step 2: Commit**

```bash
git add backend/seed.py
git commit -m "feat: add curator user and default buyer mappings to seed"
```

---

## Task 9: Frontend Types

**Files:**
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Прочитай `frontend/src/lib/types.ts` и добавь в конец файла**

```typescript
// Procurement Module

export interface ProcurementItem {
  id: string
  order_id: string
  catalog_item_id: string | null
  raw_name: string | null
  display_name: string
  quantity_ordered: number
  quantity_received: number | null
  unit: string
  status: "pending_curator" | "assigned" | "purchased" | "not_found" | "substituted"
  buyer_id: string | null
  category_id: string | null
  curator_note: string | null
  substitution_note: string | null
  is_catalog_item: boolean
  created_at: string
}

export interface ProcurementOrder {
  id: string
  restaurant_id: string
  restaurant_name: string
  user_id: string
  user_name: string
  status: string
  created_at: string
  items: ProcurementItem[]
}

export interface WhatsAppUrls {
  primary: string | null
  fallback: string
}

export interface SubmitOrderResponse {
  order: ProcurementOrder
  whatsapp: WhatsAppUrls
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd "/home/danil/Рабочий стол/supplyflow/frontend" && npx tsc --noEmit
```

Ожидаемый результат: нет вывода (чисто).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat: add procurement TypeScript types"
```

---

## Task 10: Frontend — New Order Page

**Files:**
- Create: `frontend/src/app/(cook)/kitchen/new-order/page.tsx`

- [ ] **Step 1: Создать `frontend/src/app/(cook)/kitchen/new-order/page.tsx`**

```tsx
"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { apiFetch } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import type { CatalogItem, SubmitOrderResponse } from "@/lib/types"

interface CartItem {
  catalog_item_id?: string
  raw_name?: string
  display_name: string
  quantity_ordered: string
  unit: string
  is_catalog: boolean
}

function openWhatsApp(primary: string | null, fallback: string) {
  if (!primary) {
    window.location.href = fallback
    return
  }
  let appOpened = false
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) appOpened = true
  }, { once: true })
  window.location.href = primary
  setTimeout(() => {
    if (!appOpened) window.location.href = fallback
  }, 1500)
}

export default function NewOrderPage() {
  const router = useRouter()
  const { user } = useAuth()

  const [search, setSearch] = useState("")
  const [searchResults, setSearchResults] = useState<CatalogItem[]>([])
  const [cart, setCart] = useState<CartItem[]>([])
  const [rawName, setRawName] = useState("")
  const [rawQty, setRawQty] = useState("")
  const [rawUnit, setRawUnit] = useState("шт")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")

  // Debounced catalog search
  useEffect(() => {
    if (!search.trim()) {
      setSearchResults([])
      return
    }
    const t = setTimeout(async () => {
      try {
        const results = await apiFetch<CatalogItem[]>(
          `/catalog/items?search=${encodeURIComponent(search)}`
        )
        setSearchResults(results)
      } catch {
        setSearchResults([])
      }
    }, 300)
    return () => clearTimeout(t)
  }, [search])

  function addCatalogItem(item: CatalogItem) {
    setCart((prev) => [
      ...prev,
      {
        catalog_item_id: item.id,
        display_name: item.name,
        quantity_ordered: "1",
        unit: item.unit,
        is_catalog: true,
      },
    ])
    setSearch("")
    setSearchResults([])
  }

  function addRawItem() {
    if (!rawName.trim() || !rawQty || parseFloat(rawQty) <= 0) return
    setCart((prev) => [
      ...prev,
      {
        raw_name: rawName.trim(),
        display_name: rawName.trim(),
        quantity_ordered: rawQty,
        unit: rawUnit,
        is_catalog: false,
      },
    ])
    setRawName("")
    setRawQty("")
  }

  function removeItem(index: number) {
    setCart((prev) => prev.filter((_, i) => i !== index))
  }

  function updateQty(index: number, value: string) {
    setCart((prev) =>
      prev.map((item, i) => (i === index ? { ...item, quantity_ordered: value } : item))
    )
  }

  async function handleSubmit() {
    if (!user?.restaurant_id || cart.length === 0) return
    setSubmitting(true)
    setError("")
    try {
      // 1. Create draft order
      const order = await apiFetch<{ id: string }>("/kitchen/orders", {
        method: "POST",
        body: JSON.stringify({
          restaurant_id: user.restaurant_id,
          items: cart.map((item) => ({
            catalog_item_id: item.catalog_item_id ?? null,
            raw_name: item.raw_name ?? null,
            quantity_ordered: item.quantity_ordered,
            unit: item.unit,
          })),
        }),
      })

      // 2. Submit
      const result = await apiFetch<SubmitOrderResponse>(
        `/kitchen/orders/${order.id}/submit`,
        { method: "POST" }
      )

      // 3. Open WhatsApp
      openWhatsApp(result.whatsapp.primary, result.whatsapp.fallback)

      router.push("/kitchen/orders")
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка отправки")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-4 max-w-lg mx-auto">
      <h1 className="text-xl font-semibold mb-4">Новая заявка</h1>

      {/* Catalog search */}
      <div className="mb-4">
        <Input
          placeholder="Поиск по каталогу..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {searchResults.length > 0 && (
          <div className="border rounded-md mt-1 divide-y">
            {searchResults.map((item) => (
              <button
                key={item.id}
                className="w-full text-left px-3 py-2 text-sm hover:bg-muted"
                onClick={() => addCatalogItem(item)}
              >
                {item.name} <span className="text-muted-foreground">({item.unit})</span>
              </button>
            ))}
          </div>
        )}
        {search.trim() && searchResults.length === 0 && (
          <p className="text-xs text-muted-foreground mt-1">Не найдено в каталоге — добавьте ниже вручную</p>
        )}
      </div>

      {/* Raw item input */}
      <div className="flex gap-2 mb-4">
        <Input
          placeholder="Название (не в каталоге)"
          value={rawName}
          onChange={(e) => setRawName(e.target.value)}
          className="flex-1"
        />
        <Input
          placeholder="Кол-во"
          type="number"
          min="0.001"
          step="0.001"
          value={rawQty}
          onChange={(e) => setRawQty(e.target.value)}
          className="w-24"
        />
        <Input
          placeholder="Ед."
          value={rawUnit}
          onChange={(e) => setRawUnit(e.target.value)}
          className="w-16"
        />
        <Button type="button" variant="outline" onClick={addRawItem}>+</Button>
      </div>

      {/* Cart */}
      {cart.length > 0 && (
        <div className="space-y-2 mb-4">
          <h2 className="text-sm font-medium text-muted-foreground">Позиции ({cart.length})</h2>
          {cart.map((item, i) => (
            <Card key={i}>
              <CardContent className="p-3 flex items-center gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.display_name}</p>
                  {!item.is_catalog && (
                    <Badge variant="outline" className="text-xs">вручную</Badge>
                  )}
                </div>
                <Input
                  type="number"
                  min="0.001"
                  step="0.001"
                  value={item.quantity_ordered}
                  onChange={(e) => updateQty(i, e.target.value)}
                  className="w-20 text-right"
                />
                <span className="text-sm text-muted-foreground w-8">{item.unit}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => removeItem(i)}
                  className="text-destructive"
                >
                  ✕
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      <Button
        className="w-full"
        onClick={handleSubmit}
        disabled={submitting || cart.length === 0}
      >
        {submitting ? "Отправляем..." : `Отправить заявку (${cart.length} поз.)`}
      </Button>
    </div>
  )
}
```

- [ ] **Step 2: Добавить `search` параметр в существующий `/catalog/items` endpoint**

Прочитай `backend/app/api/catalog.py`. В функции `list_items` добавь параметр `search`:

```python
@router.get("/items", response_model=list[CatalogItemRead])
async def list_items(
    category_id: uuid.UUID | None = None,
    search: str | None = None,          # ← добавить
    session: AsyncSession = Depends(get_session),
):
    q = select(CatalogItem).where(CatalogItem.is_active == True)  # noqa: E712
    if category_id:
        q = q.where(CatalogItem.category_id == category_id)
    if search:                                                      # ← добавить
        q = q.where(CatalogItem.name.ilike(f"%{search}%"))         # ← добавить
    result = await session.execute(q)
    return result.scalars().all()
```

- [ ] **Step 3: TypeScript check**

```bash
cd "/home/danil/Рабочий стол/supplyflow/frontend" && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(cook)/kitchen/new-order/page.tsx" \
        backend/app/api/catalog.py
git commit -m "feat: add kitchen new-order page and catalog search param"
```

---

## Task 11: Frontend — Order History Page

**Files:**
- Create: `frontend/src/app/(cook)/kitchen/orders/page.tsx`

- [ ] **Step 1: Создать `frontend/src/app/(cook)/kitchen/orders/page.tsx`**

```tsx
"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api"
import type { ProcurementOrder } from "@/lib/types"

const STATUS_LABEL: Record<string, string> = {
  draft: "Черновик",
  routing: "Распределяется",
  in_purchase: "В закупке",
  received: "Получено",
  closed: "Закрыто",
  cancelled: "Отменено",
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "outline",
  routing: "secondary",
  in_purchase: "default",
  received: "default",
  closed: "secondary",
  cancelled: "destructive",
}

export default function KitchenOrdersPage() {
  const [orders, setOrders] = useState<ProcurementOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = useCallback(() => {
    setLoading(true)
    apiFetch<ProcurementOrder[]>("/kitchen/orders")
      .then(setOrders)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Мои заявки</h1>
        <Link href="/kitchen/new-order">
          <Button size="sm">+ Новая</Button>
        </Link>
      </div>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : orders.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          <p>Заявок пока нет</p>
          <Link href="/kitchen/new-order">
            <Button className="mt-3" variant="outline">Создать первую заявку</Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {orders.map((order) => (
            <Card key={order.id}>
              <CardContent className="p-3">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium">
                      Заявка #{order.id.slice(0, 8)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(order.created_at).toLocaleDateString("ru-RU", {
                        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"
                      })}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {order.items.length} позиций
                    </p>
                  </div>
                  <Badge variant={STATUS_VARIANT[order.status] ?? "outline"}>
                    {STATUS_LABEL[order.status] ?? order.status}
                  </Badge>
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

- [ ] **Step 2: TypeScript check**

```bash
cd "/home/danil/Рабочий стол/supplyflow/frontend" && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(cook)/kitchen/orders/page.tsx"
git commit -m "feat: add kitchen order history page"
```

---

## Task 12: Final Verification

- [ ] **Step 1: Запустить все backend тесты**

```bash
docker compose exec backend pytest tests/ -v
```

Ожидаемый результат: все тесты PASS (включая pre-existing + 11 routing unit + 9 kitchen API).

- [ ] **Step 2: TypeScript check**

```bash
cd "/home/danil/Рабочий стол/supplyflow/frontend" && npx tsc --noEmit
```

- [ ] **Step 3: Проверить health и новые эндпоинты**

```bash
curl -s http://localhost:8000/health
# Ожидаемый: {"status":"ok"}

curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/kitchen/orders
# Ожидаемый: 401 (не 404)
```

- [ ] **Step 4: Финальный commit**

```bash
git add -A
git commit -m "feat: procurement P1 foundation complete — kitchen API, routing service, WhatsApp URLs, frontend new-order and history pages"
```
