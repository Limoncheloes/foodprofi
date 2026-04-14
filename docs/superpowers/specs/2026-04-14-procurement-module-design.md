# Procurement Module — Design Spec

**Date:** 2026-04-14  
**Project:** SupplyFlow  
**Status:** Approved — ready for implementation planning

---

## 1. Scope

Модуль закупок — это отдельный слой поверх существующей SupplyFlow системы.  
Покрывает путь от заявки повара до экспорта в 1C:

```
Повар → submit → [routing] → Закупщик → [факт] → Куратор (если нераспределено) → Печать / 1C
```

Существующий supply chain (warehouse, delivery, inventory) не затрагивается.

---

## 2. Решения по схеме

### 2.1 Отдельная таблица `procurement_items` (Variant B)

Существующая таблица `order_items` **не модифицируется**. Procurement-специфичные данные живут в отдельной таблице, связанной с существующим `orders.id`.

**Почему:** чистое разделение ответственности, существующие тесты не ломаются, таблица не засоряется nullable полями.

### 2.2 Новые роли

Добавляется одна новая роль: **`curator`** (куратор закупок).  
Роль `cook` остаётся как есть — в UI отображается "Повар".

### 2.3 Новые статусы заказа

Добавляются к существующему `OrderStatus` enum:
- `routing` — после submit, идёт автоматическая маршрутизация
- `received` — все позиции получены закупщиком
- `closed` — экспортировано в 1C, архив

Существующий flow (`in_purchase`, `at_warehouse`, etc.) не удаляется — он продолжает работать для warehouse/delivery pipeline.

### 2.4 Периодичность заявок

Повара подают заявки **в течение смены** (несколько заявок от одного ресторана в день — норма).  
Нет глобального "дедлайна на день" — каждая заявка имеет свой lifecycle.

---

## 3. Data Model

### `procurement_items`

```
id                UUID, PK
order_id          UUID, FK → orders.id (CASCADE DELETE)
catalog_item_id   UUID, FK → catalog_items.id, nullable  -- null если raw_name
raw_name          VARCHAR(255), nullable                  -- если не из каталога
quantity_ordered  DECIMAL(10,3), NOT NULL
quantity_received DECIMAL(10,3), nullable                 -- заполняет закупщик
unit              VARCHAR(50), NOT NULL                   -- берётся из catalog_item или вводится вручную
status            ENUM('pending_routing', 'pending_curator', 'assigned', 'purchased', 'not_found', 'substituted')
buyer_id          UUID, FK → users.id, nullable           -- назначенный закупщик
category_id       UUID, FK → categories.id, nullable     -- для группировки в документе
curator_note      TEXT, nullable
substitution_note TEXT, nullable                          -- если товара нет, закупщик пишет замену
is_catalog_item   BOOL, NOT NULL, default true
created_at        TIMESTAMP
updated_at        TIMESTAMP
```

**Constraint:** `CHECK (catalog_item_id IS NOT NULL OR raw_name IS NOT NULL)`  
**Constraint:** `quantity_ordered > 0`

### `routing_rules`

```
id                  UUID, PK
keyword             VARCHAR(255), NOT NULL               -- case-insensitive match в raw_name
buyer_id            UUID, FK → users.id
category_id         UUID, FK → categories.id, nullable
created_by_curator  UUID, FK → users.id
created_at          TIMESTAMP
UNIQUE (keyword)
```

### Изменения в `users`

```sql
ALTER TYPE userrole ADD VALUE 'curator';
```

### Изменения в `orders`

```sql
ALTER TYPE orderstatus ADD VALUE 'routing';
ALTER TYPE orderstatus ADD VALUE 'received';
ALTER TYPE orderstatus ADD VALUE 'closed';
```

---

## 4. API Contract

### 4.1 Cook (Повар) — /kitchen

| Method | Path | Description |
|--------|------|-------------|
| GET | `/catalog/items?search=` | Поиск по каталогу (fuzzy, уже есть `/catalog/items`, добавить `search` param) |
| POST | `/kitchen/orders` | Создать черновик procurement заявки |
| POST | `/kitchen/orders/{id}/items` | Добавить позицию (каталог или raw_name) |
| DELETE | `/kitchen/orders/{id}/items/{item_id}` | Удалить позицию |
| POST | `/kitchen/orders/{id}/submit` | Отправить заявку → статус `routing` → запустить routing сервис → `wa.me` ссылка в ответе |
| GET | `/kitchen/orders` | История заявок повара |
| GET | `/kitchen/orders/{id}` | Детали заявки |

**POST /kitchen/orders/{id}/submit — response:**
```json
{
  "order": { "id": "...", "status": "routing", ... },
  "whatsapp": {
    "primary": "whatsapp://send?groupid=120363XXX@g.us&text=...",
    "fallback": "https://wa.me/996XXXXXXXXX?text=..."
  }
}
```

`primary` = null если `WHATSAPP_GROUP_JID` не задан в env — фронт тогда сразу использует `fallback`.

**WhatsApp текст (одинаков для обоих URL):**
```
Заявка №{id} от {дата}
Ресторан: {название}

1. Говядина — 10.000 кг
2. Сыр Гауда — 5.000 кг
3. Пластиковые ложки (некаталог) — 200 шт

Статус: отправлено
```

**Fallback логика на фронтенде:**
```typescript
function openWhatsApp(primary: string | null, fallback: string) {
  if (!primary) { window.location.href = fallback; return }

  let appOpened = false
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) appOpened = true
  }, { once: true })

  window.location.href = primary  // пробуем group JID

  setTimeout(() => {
    if (!appOpened) window.location.href = fallback  // Meta сломала → куратор
  }, 1500)
}
```

### 4.2 Curator (Куратор) — /curator

| Method | Path | Description |
|--------|------|-------------|
| GET | `/curator/pending` | Позиции со статусом `pending_curator` |
| POST | `/curator/assign` | `{item_id, buyer_id, category_id?, save_rule: bool}` |
| GET | `/curator/rules` | Все правила маршрутизации |
| POST | `/curator/rules` | `{keyword, buyer_id, category_id?}` |
| PATCH | `/curator/rules/{id}` | Обновить правило |
| DELETE | `/curator/rules/{id}` | Удалить правило |
| GET | `/curator/stats` | Кол-во позиций в очереди (для бейджа) |

### 4.3 Buyer (Закупщик) — /buyer/procurement

| Method | Path | Description |
|--------|------|-------------|
| GET | `/buyer/procurement/items?date=&status=` | Мои позиции на дату |
| PATCH | `/buyer/procurement/items/{id}` | `{quantity_received, status, substitution_note?}` |
| GET | `/buyer/procurement/summary?date=` | Агрегация по категориям (для печати) |

### 4.4 Documents — /orders/{id}/export

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| GET | `/orders/{id}/export/docx` | curator, manager, admin | Word документ для печати |
| GET | `/orders/{id}/export/xlsx` | curator, manager, admin | Excel для 1C |

**Условие для xlsx:** все `procurement_items` должны иметь `quantity_received != null`.

---

## 5. Routing Logic

Запускается автоматически при `POST /kitchen/orders/{id}/submit`:

```python
for item in procurement_items:
    if item.is_catalog_item:
        buyer = item.catalog_item.category.default_buyer_id
        if buyer:
            item.buyer_id = buyer
            item.status = 'assigned'
            continue
    
    # Некаталожная или категория без дефолтного закупщика
    match = find_routing_rule(item.raw_name or item.catalog_item.name)
    if match:
        item.buyer_id = match.buyer_id
        item.category_id = match.category_id
        item.status = 'assigned'
    else:
        item.status = 'pending_curator'

# После всех позиций
if any(item.status == 'pending_curator'):
    order.status = 'routing'  # ждёт куратора
else:
    order.status = 'in_purchase'  # все назначены
```

**RoutingRule matching:** `keyword.lower() in item_name.lower()` (contains, case-insensitive).  
При нескольких совпадениях — берётся самое длинное keyword (более специфичное правило).

---

## 6. Category → Default Buyer

Существующая модель `Category` расширяется полем:
```sql
ALTER TABLE categories ADD COLUMN default_buyer_id UUID REFERENCES users(id) NULL;
```

Admin устанавливает эту связь через UI (или seed скрипт для MVP).

---

## 7. Document Templates

### Word (python-docx)

Группировка по закупщикам. Формат:
```
ЗАЯВКА НА ЗАКУПКУ №{id}
Дата: {date} | Ресторан: {restaurant_name} | Создал: {user_name}

═══════════════════════════════════════
ЗАКУПЩИК: {buyer_name} — {category_names}
═══════════════════════════════════════
№   Наименование        Заказано    Получено    Ед.
1   Говядина            10.000      _______     кг
2   Сыр Гауда           5.000       _______     кг

[следующий закупщик]
```

Шрифт: минимум 12pt. Поля: 2cm со всех сторон.

### Excel (openpyxl)

**Лист 1 — Все позиции:**
```
Дата | Номер заявки | Ресторан | Наименование | Артикул | Кол-во заказано | Кол-во получено | Ед. | Закупщик | Категория | Примечание
```

**Лист 2 — Агрегация по категориям:**
```
Категория | Наименование | Итого заказано | Итого получено | Ед.
```

⚠️ **Блокер:** Точный формат колонок согласовывается с клиентом до начала Sprint 3. Необходимо: версия 1C, шаблон импорта, формат даты, разделитель дробной части.

---

## 8. Roles & Access

| Роль | Procurement права |
|------|-------------------|
| `cook` | Создать/отредактировать/отправить свои заявки |
| `curator` | Просматривать очередь, назначать закупщиков, управлять правилами, скачивать документы |
| `buyer` | Видеть только свои назначенные позиции, вносить quantity_received и статус |
| `manager` | Читать все заявки своего ресторана, скачивать документы |
| `admin` | Всё, включая управление каталогом и дефолтными закупщиками |

---

## 9. Frontend Routes

| Route | Role | Description |
|-------|------|-------------|
| `/kitchen/new-order` | cook | Форма новой procurement заявки |
| `/kitchen/orders` | cook | История заявок |
| `/curator/queue` | curator | Очередь непереданных позиций |
| `/curator/rules` | curator | Управление правилами маршрутизации |
| `/buyer/procurement` | buyer | Мои позиции на сегодня |
| `/manager/procurement` | manager | Все заявки ресторана |

---

## 10. Environment Variables

```env
WHATSAPP_GROUP_JID=120363XXXXXXXXXX@g.us  # Внутренний JID WhatsApp группы (опционально)
WHATSAPP_CURATOR_PHONE=996XXXXXXXXX        # Номер куратора — fallback если JID не задан или сломан
```

Если `WHATSAPP_GROUP_JID` не задан — `primary` в ответе = null, фронт сразу открывает `wa.me/{CURATOR_PHONE}`.

---

## 11. Sprint Breakdown

### Procurement Sprint P1 — Foundation
- Миграции: `curator` роль, `routing`, `received`, `closed` статусы, `procurement_items`, `routing_rules`, `categories.default_buyer_id`
- Сервис routing (unit-tested)
- API: `/kitchen/orders` CRUD + submit + WhatsApp URL
- Фронт: `/kitchen/new-order`, `/kitchen/orders`
- Seed: добавить curator пользователя, дефолтные buyer→category маппинги

### Procurement Sprint P2 — Routing & Buyer
- API: `/curator/*` (queue, assign, rules CRUD)
- API: `/buyer/procurement/*` (items, update, summary)
- Фронт: `/curator/queue`, `/curator/rules`
- Фронт: `/buyer/procurement`
- Бейдж куратора (кол-во в очереди)

### Procurement Sprint P3 — Documents (после получения 1C формата)
- `GET /orders/{id}/export/docx` (python-docx)
- `GET /orders/{id}/export/xlsx` (openpyxl, формат под 1C)
- Кнопки скачивания в UI

### Procurement Sprint P4 — Polish & Pilot
- Фильтры, история, дашборд менеджера
- Admin: привязка дефолтных закупщиков к категориям
- Деплой Hetzner, пилот 2–3 ресторана

---

## 12. Key Constraints (never violate)

- `quantity_ordered` — immutable после submit. Никогда не изменяется.
- `routing_rules.keyword` — накапливаются, не удаляются автоматически.
- Excel экспорт — только после того как все позиции имеют `quantity_received`.
- WhatsApp — только `wa.me` ссылка, без Business API.
- Word документ — python-docx, без конвертации в PDF на Phase 1.
- Существующие `order_items` и warehouse/delivery pipeline — не трогать.
