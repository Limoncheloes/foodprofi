# Procurement P4 — Polish & Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дашборд менеджера, фильтры и история заявок, admin UI для привязки закупщиков к категориям, деплой на Hetzner и пилот с 2–3 ресторанами.

**Architecture:** Минимальные изменения поверх P1–P3. Менеджер видит все заявки своего ресторана через существующий `/kitchen/orders` с расширенной фильтрацией. Привязка buyer→category через новый admin эндпоинт. Деплой — обновление docker-compose.yml для продакшена.

**Tech Stack:** FastAPI + Next.js + Docker Compose + Hetzner VPS

**Prerequisite:** P3 план полностью выполнен. Пилот согласован с 2–3 ресторанами.

---

## File Map

### Backend — Modified Files
| File | Change |
|------|--------|
| `backend/app/api/kitchen.py` | Добавить фильтры по дате и статусу в `GET /kitchen/orders` |
| `backend/app/api/admin.py` | Добавить `PATCH /admin/categories/{id}` для установки `default_buyer_id` |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/app/(manager)/manager/procurement/page.tsx` | Дашборд менеджера: все заявки ресторана с фильтрами |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `frontend/src/app/(cook)/kitchen/orders/page.tsx` | Добавить фильтр по статусу |

### Infrastructure
| File | Change |
|------|--------|
| `docker-compose.prod.yml` | Production compose с SSL, env из секретов |
| `.env.prod.example` | Шаблон env для продакшена |

---

## Task 1: Kitchen Orders Filters

**Files:**
- Modify: `backend/app/api/kitchen.py`

- [ ] **Step 1: Прочитай `backend/app/api/kitchen.py`**

Найди функцию `list_procurement_orders`. Добавь параметры фильтрации:

```python
@router.get("/orders", response_model=list[ProcurementOrderRead])
async def list_procurement_orders(
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    restaurant_id: uuid.UUID | None = None,
    current_user: User = Depends(role_required(*_COOK_ROLES, UserRole.manager, UserRole.curator, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> list[ProcurementOrderRead]:
    q = (
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
        .order_by(Order.created_at.desc())
    )
    # Cook and manager see only their restaurant
    if current_user.role == UserRole.cook:
        q = q.where(Order.restaurant_id == current_user.restaurant_id)
    elif current_user.role == UserRole.manager:
        q = q.where(Order.restaurant_id == current_user.restaurant_id)
    elif restaurant_id:
        q = q.where(Order.restaurant_id == restaurant_id)

    if status:
        try:
            q = q.where(Order.status == OrderStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    if date_from:
        q = q.where(Order.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        q = q.where(Order.created_at <= datetime.combine(date_to, time.max))

    orders_result = await session.execute(q)
    orders = orders_result.scalars().all()
    # ... остальной код без изменений
```

Добавь импорт `from datetime import date, time, datetime` в начало файла если его нет.

- [ ] **Step 2: Запустить тесты**

```bash
docker compose exec backend pytest tests/test_kitchen.py -v
```

Ожидаемый результат: все тесты PASS (фильтры не ломают существующие тесты).

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/kitchen.py
git commit -m "feat: add date and status filters to kitchen orders list"
```

---

## Task 2: Admin — Set Default Buyer for Category

**Files:**
- Modify: `backend/app/api/admin.py`

- [ ] **Step 1: Прочитай `backend/app/api/admin.py`**

Найди место для добавления нового эндпоинта. Добавь в конец файла:

```python
class CategoryBuyerUpdate(BaseModel):
    default_buyer_id: uuid.UUID | None

@router.patch("/categories/{category_id}/buyer", response_model=CategoryRead)
async def set_category_default_buyer(
    category_id: uuid.UUID,
    body: CategoryBuyerUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(role_required(UserRole.admin)),
):
    """Set or clear the default buyer for a category (used in auto-routing)."""
    from app.models.catalog import Category
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
```

- [ ] **Step 2: Добавить тест**

В `backend/tests/test_catalog.py` или создать `backend/tests/test_admin_category.py`:

```python
async def test_admin_sets_default_buyer_for_category(client, admin_token):
    from httpx import AsyncClient
    cat = await client.post(
        "/catalog/categories", json={"name": "Мясо", "sort_order": 1}, headers=admin_token
    )
    cat_id = cat.json()["id"]

    # Register a buyer
    buyer_resp = await client.post(
        "/auth/register",
        json={"phone": "+99699111001", "password": "p", "name": "B", "role": "buyer"},
    )
    buyer_id = buyer_resp.json()["id"]

    resp = await client.patch(
        f"/admin/categories/{cat_id}/buyer",
        json={"default_buyer_id": buyer_id},
        headers=admin_token,
    )
    assert resp.status_code == 200
    assert resp.json()["default_buyer_id"] == buyer_id
```

- [ ] **Step 3: Запустить тест**

```bash
docker compose exec backend pytest tests/test_admin_category.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/admin.py backend/tests/test_admin_category.py
git commit -m "feat: add admin endpoint to set default buyer for category"
```

---

## Task 3: Manager Dashboard

**Files:**
- Create: `frontend/src/app/(manager)/manager/procurement/page.tsx`

- [ ] **Step 1: Создать `frontend/src/app/(manager)/manager/procurement/page.tsx`**

```tsx
"use client"

import { useCallback, useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
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

export default function ManagerProcurementPage() {
  const [orders, setOrders] = useState<ProcurementOrder[]>([])
  const [filter, setFilter] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = useCallback((status?: string) => {
    setLoading(true)
    const params = status ? `?status=${status}` : ""
    apiFetch<ProcurementOrder[]>(`/kitchen/orders${params}`)
      .then(setOrders)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load(filter || undefined) }, [load, filter])

  const statuses = ["", "draft", "routing", "in_purchase", "received", "closed"]

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">Заявки ресторана</h1>

      {/* Status filter */}
      <div className="flex gap-1 flex-wrap mb-4">
        {statuses.map((s) => (
          <Button
            key={s}
            size="sm"
            variant={filter === s ? "default" : "outline"}
            onClick={() => setFilter(s)}
          >
            {s ? (STATUS_LABEL[s] ?? s) : "Все"}
          </Button>
        ))}
      </div>

      {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

      {loading ? (
        <p className="text-center text-muted-foreground">Загрузка...</p>
      ) : orders.length === 0 ? (
        <p className="text-center text-muted-foreground py-8">Нет заявок</p>
      ) : (
        <div className="space-y-2">
          {orders.map((order) => (
            <Card key={order.id}>
              <CardContent className="p-3">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-sm">#{order.id.slice(0, 8)}</p>
                    <p className="text-xs text-muted-foreground">
                      {order.user_name} · {new Date(order.created_at).toLocaleString("ru-RU", {
                        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"
                      })}
                    </p>
                    <p className="text-xs text-muted-foreground">{order.items.length} позиций</p>
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
git add "frontend/src/app/(manager)/manager/procurement/page.tsx"
git commit -m "feat: add manager procurement dashboard with status filters"
```

---

## Task 4: Production Deploy Checklist

- [ ] **Step 1: Создать `docker-compose.prod.yml`**

Прочитай существующий `docker-compose.yml`. Создай `docker-compose.prod.yml` с:
- `restart: always` на всех сервисах
- `DEBUG=false` в backend env
- Caddy или nginx для SSL termination
- Убрать exposed порты postgres и minio (только internal network)
- Volumes с named mounts (не bind mounts)

- [ ] **Step 2: Создать `.env.prod.example`**

```env
# Database
DATABASE_URL=postgresql+asyncpg://supplyflow:STRONG_PASSWORD@postgres/supplyflow

# Security
SECRET_KEY=GENERATE_WITH_openssl_rand_-hex_32

# App
DEBUG=false
BACKEND_CORS_ORIGINS=https://your-domain.com

# MinIO
MINIO_ROOT_USER=supplyflow
MINIO_ROOT_PASSWORD=STRONG_MINIO_PASSWORD
MINIO_BUCKET=supplyflow

# WhatsApp
WHATSAPP_GROUP_JID=120363XXXXXXXXXX@g.us
WHATSAPP_CURATOR_PHONE=996XXXXXXXXX
```

- [ ] **Step 3: Деплой на Hetzner**

```bash
# На сервере:
git clone <repo> /srv/supplyflow
cd /srv/supplyflow
cp .env.prod.example .env
# Заполнить .env реальными значениями

docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.prod.yml exec backend python seed.py
```

- [ ] **Step 4: Smoke test на проде**

```bash
curl -s https://your-domain.com/health
# Ожидаемый: {"status":"ok"}
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.prod.yml .env.prod.example
git commit -m "feat: add production docker-compose and env template"
```

---

## Task 5: Pilot Preparation Checklist

- [ ] Создать пользователей для каждого пилотного ресторана (admin панель)
- [ ] Загрузить каталог товаров (минимум топ-50 позиций пилотных ресторанов)
- [ ] Настроить `default_buyer_id` для каждой категории
- [ ] Добавить начальные routing rules для частых некаталожных позиций
- [ ] Провести онбординг с поварами (5 минут: как создать и отправить заявку)
- [ ] Провести онбординг с куратором (10 минут: очередь, назначение, правила)
- [ ] Провести онбординг с закупщиками (5 минут: мои позиции, ввод факта)
- [ ] Заполнить `WHATSAPP_GROUP_JID` номером закупочной группы
- [ ] Убедиться что WhatsApp fallback работает (проверить с реальным телефоном)

- [ ] **Финальный commit**

```bash
git add -A
git commit -m "feat: procurement P4 complete — filters, manager dashboard, production deploy"
```
