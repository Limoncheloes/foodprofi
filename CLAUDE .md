# Project: SupplyFlow

## Overview
SupplyFlow is a B2B food procurement and delivery management platform for a distribution company serving 50+ restaurants in Bishkek. It replaces the current chaos of WhatsApp groups, manual overnight rewriting, and head-based inventory tracking with a structured digital workflow.

**Stack:** Python FastAPI + Next.js (App Router) + PostgreSQL + MinIO + Docker Compose
**Phase:** MVP — function and logic ONLY. No design system, no branding, no visual polish. Use default shadcn/ui components as-is. Design phase comes later.

## Problem Being Solved
Current flow: Restaurant staff (cooks, bartenders, cleaners) → WhatsApp messages (unstructured) → Night operators manually rewrite orders → Buyers group chat → Buyers go to bazaar/butchers at dawn → Warehouse sorts and packs → Drivers deliver to restaurants. Urgent morning orders, returns, and comments all live in chat threads.

**What we eliminate:** Night operators (auto-aggregation replaces manual rewriting), head-based inventory (digital stock tracking), scattered WhatsApp chaos (structured catalog ordering), lost feedback (in-system returns and comments).

## Architecture

```
supplyflow/
├── docker-compose.yml          # postgres, backend, frontend, minio
├── .env.example                # all env vars documented here
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── main.py             # FastAPI app, CORS, lifespan
│   │   ├── config.py           # pydantic-settings, env vars
│   │   ├── database.py         # async SQLAlchemy engine + session
│   │   ├── auth/
│   │   │   ├── router.py       # login, register, refresh
│   │   │   ├── dependencies.py # get_current_user, role_required
│   │   │   ├── jwt.py          # token create/verify
│   │   │   └── schemas.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── restaurant.py
│   │   │   ├── catalog.py      # CatalogItem + Category
│   │   │   ├── order.py        # Order + OrderItem
│   │   │   ├── inventory.py
│   │   │   ├── delivery.py
│   │   │   └── feedback.py
│   │   ├── schemas/            # Pydantic v2 schemas (one file per domain)
│   │   ├── api/
│   │   │   ├── catalog.py
│   │   │   ├── orders.py
│   │   │   ├── aggregation.py  # GET aggregated orders for buyers
│   │   │   ├── inventory.py
│   │   │   ├── delivery.py
│   │   │   ├── feedback.py
│   │   │   └── admin.py        # user management, restaurant CRUD
│   │   └── services/
│   │       ├── aggregator.py   # aggregate all orders by category, subtract stock
│   │       ├── stock.py        # inventory operations: receive, consume, check
│   │       └── notifications.py # (phase 2) push notifications
│   └── tests/
│       ├── conftest.py         # async test client, test DB
│       └── test_orders.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.js
    ├── public/
    │   └── manifest.json       # PWA manifest
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx      # root layout, auth provider
    │   │   ├── page.tsx        # login/landing
    │   │   ├── (cook)/         # cook interface routes
    │   │   │   ├── catalog/    # browse catalog, add to cart
    │   │   │   ├── cart/       # review and submit order
    │   │   │   ├── orders/     # order history
    │   │   │   └── templates/  # saved order templates
    │   │   ├── (buyer)/        # buyer interface routes
    │   │   │   ├── dashboard/  # aggregated orders view
    │   │   │   ├── purchase/   # mark as purchased
    │   │   │   └── stock/      # current inventory
    │   │   ├── (warehouse)/    # warehouse interface routes
    │   │   │   ├── receiving/  # mark incoming goods
    │   │   │   └── packing/    # checklists per restaurant
    │   │   ├── (driver)/       # driver interface routes
    │   │   │   ├── routes/     # today's delivery list
    │   │   │   └── confirm/    # photo confirmation
    │   │   └── (admin)/        # admin panel
    │   │       ├── users/
    │   │       ├── restaurants/
    │   │       └── catalog/
    │   ├── components/
    │   │   └── ui/             # shadcn/ui components (default styling)
    │   ├── lib/
    │   │   ├── api.ts          # fetch wrapper with auth headers
    │   │   ├── auth.tsx        # auth context + hooks
    │   │   └── types.ts        # shared TypeScript types
    │   └── middleware.ts       # route protection by role
    └── tailwind.config.ts
```

## Database Models (Core)

### Users
- id (UUID, PK), name, phone (unique), password_hash, role (enum: cook, buyer, warehouse, driver, admin), restaurant_id (FK, nullable — buyers/drivers may not belong to one restaurant), created_at

### Restaurants
- id (UUID, PK), name, address, contact_phone, is_active, created_at

### Categories
- id (UUID, PK), name (e.g. "Мясо", "Молочка", "Овощи", "Химия"), sort_order

### CatalogItems
- id (UUID, PK), category_id (FK), name, unit (enum: kg, pcs, liters, packs), variants (JSON array, e.g. ["с костью", "без кости"]), is_active, created_at

### Orders
- id (UUID, PK), user_id (FK), restaurant_id (FK), status (enum: draft, submitted, in_purchase, at_warehouse, packed, in_delivery, delivered, cancelled), is_urgent (bool), deadline (datetime), created_at, updated_at

### OrderItems
- id (UUID, PK), order_id (FK), catalog_item_id (FK), quantity (float), variant (string, nullable), note (text, nullable)

### Inventory
- id (UUID, PK), catalog_item_id (FK, unique), quantity (float), updated_at
- Operations tracked via InventoryLog: item_id, delta, reason (received/consumed/adjusted), user_id, created_at

### Deliveries
- id (UUID, PK), order_id (FK), driver_id (FK to Users), status (enum: loading, en_route, delivered), photo_url (string, nullable), delivered_at (datetime, nullable)

### Feedback
- id (UUID, PK), order_id (FK), user_id (FK), type (enum: return, quality_issue, missing_item, other), comment (text), photo_url (nullable), created_at

## User Roles & Permissions

| Role | Can do | Cannot do |
|------|--------|-----------|
| cook | Create orders for own restaurant, use templates, view own order history, submit feedback | See other restaurants' orders, modify catalog |
| buyer | View aggregated orders, mark purchases, manage inventory, see all restaurants | Create orders, manage users |
| warehouse | Receive goods, pack orders per restaurant, update inventory | Create orders, see financials |
| driver | View delivery routes, confirm deliveries with photo | Modify orders, manage inventory |
| admin | Everything: manage users, restaurants, catalog, view all data | — |

## Key API Endpoints (plan)

### Auth
- POST /auth/register — phone + password + role (admin only can create buyers/warehouse/drivers)
- POST /auth/login — returns JWT access + refresh tokens
- POST /auth/refresh — refresh token rotation

### Catalog
- GET /catalog/categories — list categories
- GET /catalog/items?category_id= — items in category
- POST /catalog/items — admin: create item
- PATCH /catalog/items/{id} — admin: update item

### Orders
- POST /orders — cook: create order (with items)
- GET /orders?restaurant_id=&status= — filtered order list
- GET /orders/{id} — order detail with items
- PATCH /orders/{id}/status — advance status (role-dependent)
- POST /orders/from-template/{template_id} — create order from template

### Aggregation (buyer dashboard)
- GET /aggregation/summary?date= — all orders for date, grouped by category, with stock subtracted
- POST /aggregation/mark-purchased — buyer marks items as purchased with actual quantities and prices

### Inventory
- GET /inventory — current stock levels
- POST /inventory/receive — warehouse: record incoming goods
- POST /inventory/adjust — manual adjustment with reason

### Delivery
- GET /deliveries/today — driver: today's deliveries
- PATCH /deliveries/{id}/confirm — driver: confirm with photo upload

### Feedback
- POST /feedback — any role: create feedback on an order
- GET /feedback?order_id= — feedback for an order

## Development Rules

### Backend
- Every endpoint: router (thin) + service (business logic) + schema (validation). Never put logic in routers.
- All DB operations: async SQLAlchemy with `async_session`. Use `select()` style, not legacy `query()`.
- Migrations: always through `alembic revision --autogenerate -m "description"`. Never raw SQL for schema changes.
- Auth: JWT with short-lived access token (30min) + long-lived refresh token (7 days). Phone number as login.
- Env vars: every new config value goes in `config.py` (pydantic-settings) AND `.env.example`.
- Tests: pytest + httpx async client. At minimum: test auth flow, test order creation, test aggregation logic.

### Frontend
- Phase 1: use shadcn/ui components with ZERO custom styling. Default theme, default colors. Function first.
- Every page: loading state + error state + empty state. Use React Suspense where possible.
- Auth: store JWT in httpOnly cookie (preferred) or localStorage. Auth context wraps the app.
- API calls: centralized in `lib/api.ts` with automatic token refresh on 401.
- Forms: use react-hook-form + zod validation. Match Pydantic schemas.
- Mobile-first: all interfaces must work on phone screens. Most users are on mobile.
- Localization: Russian language for all UI text. Hardcode for MVP, i18n comes later.
- PWA: manifest.json + basic service worker for installability. No offline mode needed (stable WiFi confirmed).

### General
- Monorepo: one git repo, one docker-compose.yml.
- Branch strategy: `main` (production) + feature branches. Merge via PR.
- Commit messages: conventional commits (feat:, fix:, refactor:, etc.).
- No premature optimization. No caching layer for MVP. No WebSockets for MVP — polling is fine.
- Error handling: backend returns consistent error shape `{detail: string, code: string}`. Frontend shows toast.

## Commands
- `docker compose up -d` — start all services
- `docker compose exec backend alembic upgrade head` — apply migrations
- `docker compose exec backend alembic revision --autogenerate -m "msg"` — create migration
- `docker compose exec backend pytest tests/ -v` — run backend tests
- `cd frontend && npm run dev` — frontend dev server (if working outside Docker)
- `docker compose logs -f backend` — tail backend logs

## Sprint Plan

### Sprint 1: Foundation + Cook ordering (weeks 1-2)
1. Docker Compose setup: postgres + backend + frontend + minio
2. Auth system: register, login, JWT, role middleware
3. Admin: CRUD for restaurants, users, catalog categories, catalog items
4. Cook interface: browse catalog by category → add to cart → submit order
5. PWA manifest (installable on phone)
6. Seed script: populate test data (5 restaurants, 50 catalog items, 10 users)

### Sprint 2: Buyer dashboard + aggregation (weeks 3-4)
1. Aggregation service: collect all submitted orders → group by category → subtract inventory
2. Buyer dashboard: view aggregated needs, filter by category
3. "Mark as purchased": buyer records what was actually bought (quantity + price)
4. Order templates: cook can save an order as template, reuse with quantity edits
5. Order status flow: submitted → in_purchase → at_warehouse

### Sprint 3: Warehouse + delivery (weeks 5-6)
1. Inventory tracking: receive goods (from buyer purchase), manual adjustments
2. Warehouse packing: checklists per restaurant (what goes where)
3. Status: at_warehouse → packed → in_delivery
4. Driver interface: today's route, confirm delivery with photo
5. MinIO integration for photo uploads

### Sprint 4: Feedback + urgent orders + polish (weeks 7-8)
1. Feedback system: returns, quality issues, missing items — with photos
2. Urgent orders: orders submitted after deadline get flagged, handled separately
3. Push notifications (PWA): notify buyer when orders are ready, notify cook when delivered
4. Testing on 2-3 real restaurants
5. Bug fixes from real usage

## Plugin Usage (Claude Code)
- **superpowers**: use for planning each sprint, TDD for critical services (aggregator, stock)
- **feature-dev**: use for each major feature ("сделай авторизацию", "добавь дашборд закупщика")
- **context7**: will auto-pull FastAPI and Next.js docs — let it work
- **code-review**: run before every commit
- **commit-commands**: use for all commits and PRs
- **github**: use for issue tracking and PR management

## Recommended Workflow
1. Start sprint: `/superpowers:write-plan` with sprint goals from above
2. Each feature: use feature-dev plugin ("добавь CRUD каталога")
3. Before commit: code-review plugin
4. Commit: commit-commands plugin
5. End of sprint: `/security-audit` on the whole project
6. After Sprint 4: `/superpowers:brainstorm` for design phase planning

## Known Constraints
- All UI in Russian language
- Users are non-technical (cooks, warehouse workers) — UI must be dead simple
- Orders have a nightly deadline (e.g., 22:00) — after that, marked as urgent
- Catalog items can have variants (e.g., "с костью" / "без кости") — stored as JSON array
- Inventory is approximate — exact gram-level tracking is not needed
- Single warehouse, single delivery batch per day (for MVP)

## Current Focus
Sprint 1: Docker Compose setup + Auth + Catalog CRUD + Cook ordering interface.
Start with backend, then frontend. Get the first order flowing end-to-end.
