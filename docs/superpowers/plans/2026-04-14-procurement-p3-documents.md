# Procurement P3 — Documents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать генерацию Word-документа для печати (python-docx) и Excel-экспорта для 1C (openpyxl). Кнопки скачивания в UI для куратора и менеджера.

**Architecture:** Два новых эндпоинта на существующем `/orders` роутере. Сервис `backend/app/services/documents.py` содержит всю логику генерации — изолирован от роутера. Excel формат финализируется с клиентом до начала спринта.

**Tech Stack:** python-docx + openpyxl | FastAPI StreamingResponse | Next.js fetch + blob download

**Prerequisite:** P2 план полностью выполнен. **ВАЖНО: Формат 1C согласован с клиентом.**

---

## Перед началом: получить от клиента

Перед написанием `generate_xlsx` уточни у клиента:
1. Версию 1C (УТ 11, ERP, Рестораны 8.3, другая)
2. Скриншот формы импорта или шаблон .xlsx для импорта
3. Названия и порядок обязательных колонок
4. Формат даты (ДД.ММ.ГГГГ или ГГГГ-ММ-ДД)
5. Разделитель дробной части (точка или запятая)

Запиши ответы в `.claude/specs/1c-format.md` и обнови раздел Excel ниже.

---

## File Map

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `backend/app/services/documents.py` | Генерация DOCX и XLSX: `generate_docx(order, items)`, `generate_xlsx(order, items)` |
| `backend/tests/test_documents.py` | Тесты генерации документов |

### Backend — Modified Files
| File | Change |
|------|--------|
| `backend/requirements.txt` | Добавить `python-docx` и `openpyxl` |
| `backend/app/api/orders.py` | Добавить два эндпоинта: `GET /orders/{id}/export/docx` и `GET /orders/{id}/export/xlsx` |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `frontend/src/app/(curator)/curator/queue/page.tsx` | Добавить кнопку "Скачать для печати" на деталях заявки |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Прочитай `backend/requirements.txt` и добавь строки**

```
python-docx==1.1.2
openpyxl==3.1.5
```

- [ ] **Step 2: Установить в контейнер**

```bash
docker compose exec backend pip install python-docx==1.1.2 openpyxl==3.1.5
```

Ожидаемый результат: `Successfully installed python-docx-1.1.2 openpyxl-3.1.5`

- [ ] **Step 3: Пересобрать образ чтобы зависимости были в Dockerfile**

```bash
docker compose build backend
docker compose up -d backend
```

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat: add python-docx and openpyxl dependencies"
```

---

## Task 2: Document Generation Service

**Files:**
- Create: `backend/app/services/documents.py`
- Create: `backend/tests/test_documents.py`

- [ ] **Step 1: Написать failing tests — `backend/tests/test_documents.py`**

```python
"""Tests for document generation service."""
import io
import pytest
from unittest.mock import MagicMock
import uuid
from datetime import datetime


def make_order(rest_name="Ресторан 1", user_name="Повар Иван"):
    order = MagicMock()
    order.id = uuid.uuid4()
    order.restaurant_name = rest_name
    order.user_name = user_name
    order.created_at = datetime(2026, 4, 14, 10, 30)
    return order


def make_item(name="Говядина", qty_ordered=10.0, qty_received=None,
              unit="кг", buyer_name="Айбек", cat_name="Мясо"):
    item = MagicMock()
    item.display_name = name
    item.quantity_ordered = qty_ordered
    item.quantity_received = qty_received
    item.unit = unit
    item.buyer_name = buyer_name
    item.category_name = cat_name
    item.raw_name = None
    item.is_catalog_item = True
    item.substitution_note = None
    return item


def test_generate_docx_returns_bytes():
    from app.services.documents import generate_docx
    order = make_order()
    items = [make_item(), make_item("Молоко", 5.0, unit="л", cat_name="Молочка")]
    result = generate_docx(order, items)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_docx_valid_word_file():
    """Output must be a valid .docx (ZIP) file."""
    import zipfile
    from app.services.documents import generate_docx
    order = make_order()
    items = [make_item()]
    result = generate_docx(order, items)
    buf = io.BytesIO(result)
    assert zipfile.is_zipfile(buf), "Output is not a valid ZIP/docx file"


def test_generate_xlsx_returns_bytes():
    from app.services.documents import generate_xlsx
    order = make_order()
    items = [make_item(), make_item("Картофель", 20.0, qty_received=18.5, unit="кг")]
    result = generate_xlsx(order, items)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_xlsx_valid_excel_file():
    """Output must be a valid .xlsx file readable by openpyxl."""
    import openpyxl
    from app.services.documents import generate_xlsx
    order = make_order()
    items = [make_item(qty_received=9.0)]
    result = generate_xlsx(order, items)
    wb = openpyxl.load_workbook(io.BytesIO(result))
    assert len(wb.sheetnames) >= 2  # Sheet1 = all items, Sheet2 = summary


def test_generate_xlsx_sheet1_has_correct_columns():
    import openpyxl
    from app.services.documents import generate_xlsx, XLSX_COLUMNS
    order = make_order()
    items = [make_item(qty_received=9.0)]
    result = generate_xlsx(order, items)
    wb = openpyxl.load_workbook(io.BytesIO(result))
    ws = wb.active
    headers = [ws.cell(row=1, column=i).value for i in range(1, len(XLSX_COLUMNS) + 1)]
    assert headers == XLSX_COLUMNS


def test_generate_xlsx_data_row_correct():
    import openpyxl
    from app.services.documents import generate_xlsx
    order = make_order(rest_name="Ресторан Тест")
    item = make_item("Говядина", qty_ordered=10.0, qty_received=9.5, unit="кг")
    result = generate_xlsx(order, [item])
    wb = openpyxl.load_workbook(io.BytesIO(result))
    ws = wb.active
    row = [ws.cell(row=2, column=i).value for i in range(1, 12)]
    assert "Ресторан Тест" in row
    assert "Говядина" in row
    assert 10.0 in row
    assert 9.5 in row
```

- [ ] **Step 2: Запустить — ожидать FAIL**

```bash
docker compose exec backend pytest tests/test_documents.py -v
```

Ожидаемый результат: `ImportError: cannot import name 'generate_docx'`

- [ ] **Step 3: Создать `backend/app/services/documents.py`**

```python
"""Document generation service for procurement orders.

Generates:
- DOCX (python-docx): printable order sheet grouped by buyer
- XLSX (openpyxl): 1C import format, two sheets

Both functions accept plain data objects (dicts or mock-friendly objects)
so they can be unit-tested without a database.
"""
import io
from typing import Any

from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment


# Excel column headers — update to match client's 1C import template
XLSX_COLUMNS = [
    "Дата",
    "Номер заявки",
    "Ресторан",
    "Наименование",
    "Артикул",
    "Кол-во заказано",
    "Кол-во получено",
    "Ед. изм.",
    "Закупщик",
    "Категория",
    "Примечание",
]


def generate_docx(order: Any, items: list[Any]) -> bytes:
    """Generate a printable Word document grouped by buyer.

    order attributes used: id, restaurant_name, user_name, created_at
    item attributes used: display_name, quantity_ordered, quantity_received,
                          unit, buyer_name, category_name
    """
    doc = Document()

    # Page margins: 2cm all sides
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)

    # Title
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(f"ЗАЯВКА НА ЗАКУПКУ №{str(order.id)[:8].upper()}")
    run.bold = True
    run.font.size = Pt(14)

    # Header info
    date_str = order.created_at.strftime("%d.%m.%Y")
    info = doc.add_paragraph()
    info.add_run(
        f"Дата: {date_str}  |  Ресторан: {order.restaurant_name}  |  Создал: {order.user_name}"
    ).font.size = Pt(11)

    doc.add_paragraph()  # spacer

    # Group items by buyer
    buyers: dict[str, list[Any]] = {}
    for item in items:
        buyer_name = getattr(item, "buyer_name", None) or "Не назначен"
        buyers.setdefault(buyer_name, []).append(item)

    for buyer_name, buyer_items in buyers.items():
        # Buyer separator
        sep = doc.add_paragraph()
        sep.add_run("─" * 60)

        buyer_header = doc.add_paragraph()
        run = buyer_header.add_run(f"ЗАКУПЩИК: {buyer_name}")
        run.bold = True
        run.font.size = Pt(12)

        sep2 = doc.add_paragraph()
        sep2.add_run("─" * 60)

        # Table
        table = doc.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        for cell, text in zip(hdr, ["№", "Наименование", "Заказано", "Получено", "Ед."]):
            hdr_run = cell.paragraphs[0].add_run(text)
            hdr_run.bold = True
            hdr_run.font.size = Pt(11)

        for idx, item in enumerate(buyer_items, 1):
            row = table.add_row().cells
            qty_ordered = f"{float(item.quantity_ordered):.3f}"
            qty_received = "_______" if item.quantity_received is None else f"{float(item.quantity_received):.3f}"
            for cell, text in zip(row, [str(idx), item.display_name, qty_ordered, qty_received, item.unit]):
                cell.paragraphs[0].add_run(text).font.size = Pt(12)

        doc.add_paragraph()  # spacer between buyers

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def generate_xlsx(order: Any, items: list[Any]) -> bytes:
    """Generate an Excel file for 1C import.

    Sheet 1: all items (one row per item)
    Sheet 2: summary aggregated by category

    order attributes: id, restaurant_name, created_at
    item attributes: display_name, quantity_ordered, quantity_received,
                     unit, buyer_name, category_name, substitution_note
    """
    wb = openpyxl.Workbook()

    # ── Sheet 1: All items ──
    ws1 = wb.active
    ws1.title = "Все позиции"

    header_font = Font(bold=True, size=11)
    header_fill = PatternFill("solid", fgColor="D9D9D9")

    for col_idx, col_name in enumerate(XLSX_COLUMNS, 1):
        cell = ws1.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    date_str = order.created_at.strftime("%d.%m.%Y")
    order_short = str(order.id)[:8].upper()

    for row_idx, item in enumerate(items, 2):
        note = getattr(item, "substitution_note", None) or ""
        ws1.cell(row=row_idx, column=1, value=date_str)
        ws1.cell(row=row_idx, column=2, value=order_short)
        ws1.cell(row=row_idx, column=3, value=order.restaurant_name)
        ws1.cell(row=row_idx, column=4, value=item.display_name)
        ws1.cell(row=row_idx, column=5, value="")  # артикул — пусто для некаталожных
        ws1.cell(row=row_idx, column=6, value=float(item.quantity_ordered))
        ws1.cell(row=row_idx, column=7, value=float(item.quantity_received) if item.quantity_received is not None else None)
        ws1.cell(row=row_idx, column=8, value=item.unit)
        ws1.cell(row=row_idx, column=9, value=getattr(item, "buyer_name", ""))
        ws1.cell(row=row_idx, column=10, value=getattr(item, "category_name", ""))
        ws1.cell(row=row_idx, column=11, value=note)

    # Auto-width columns
    for col in ws1.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=0)
        ws1.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    # ── Sheet 2: Summary by category ──
    ws2 = wb.create_sheet("По категориям")
    summary_headers = ["Категория", "Наименование", "Итого заказано", "Итого получено", "Ед. изм."]
    for col_idx, col_name in enumerate(summary_headers, 1):
        cell = ws2.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill

    for row_idx, item in enumerate(items, 2):
        ws2.cell(row=row_idx, column=1, value=getattr(item, "category_name", "") or "Без категории")
        ws2.cell(row=row_idx, column=2, value=item.display_name)
        ws2.cell(row=row_idx, column=3, value=float(item.quantity_ordered))
        ws2.cell(row=row_idx, column=4, value=float(item.quantity_received) if item.quantity_received is not None else None)
        ws2.cell(row=row_idx, column=5, value=item.unit)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

- [ ] **Step 4: Запустить тесты — ожидать PASS**

```bash
docker compose exec backend pytest tests/test_documents.py -v
```

Ожидаемый результат: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/documents.py backend/tests/test_documents.py
git commit -m "feat: add document generation service (DOCX + XLSX)"
```

---

## Task 3: Export API Endpoints

**Files:**
- Modify: `backend/app/api/orders.py`

- [ ] **Step 1: Прочитай `backend/app/api/orders.py`**

Найди место для добавления новых эндпоинтов (в конец файла).

- [ ] **Step 2: Добавить импорты в `orders.py`**

В блок импортов добавь:

```python
from fastapi.responses import StreamingResponse
import io
from app.models.procurement import ProcurementItem
from app.models.catalog import Category
from app.models.user import User as UserModel
from app.services.documents import generate_docx, generate_xlsx
```

- [ ] **Step 3: Добавить вспомогательную функцию и два эндпоинта в конец `orders.py`**

```python
async def _load_export_items(session, order_id):
    """Load procurement items with buyer and category names for export."""
    from sqlalchemy.orm import selectinload
    result = await session.execute(
        select(ProcurementItem)
        .where(ProcurementItem.order_id == order_id)
        .options(
            selectinload(ProcurementItem.catalog_item),
            selectinload(ProcurementItem.category),
            selectinload(ProcurementItem.buyer),
        )
        .order_by(ProcurementItem.buyer_id, ProcurementItem.created_at)
    )
    items = result.scalars().all()

    class ExportItem:
        def __init__(self, pi):
            self.display_name = pi.display_name
            self.quantity_ordered = pi.quantity_ordered
            self.quantity_received = pi.quantity_received
            self.unit = pi.unit
            self.buyer_name = pi.buyer.name if pi.buyer else "Не назначен"
            self.category_name = pi.category.name if pi.category else ""
            self.substitution_note = pi.substitution_note
            self.is_catalog_item = pi.is_catalog_item
            self.raw_name = pi.raw_name

    return [ExportItem(i) for i in items]


@router.get("/orders/{order_id}/export/docx")
async def export_order_docx(
    order_id: uuid.UUID,
    current_user=Depends(role_required(UserRole.curator, UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items = await _load_export_items(session, order_id)
    if not items:
        raise HTTPException(status_code=400, detail="Order has no procurement items")

    docx_bytes = generate_docx(order, items)
    filename = f"zakupka_{str(order_id)[:8]}.docx"
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/orders/{order_id}/export/xlsx")
async def export_order_xlsx(
    order_id: uuid.UUID,
    current_user=Depends(role_required(UserRole.curator, UserRole.manager, UserRole.admin)),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.user), selectinload(Order.restaurant))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items = await _load_export_items(session, order_id)
    if not items:
        raise HTTPException(status_code=400, detail="Order has no procurement items")

    # Validate all items have quantity_received before 1C export
    missing = [i.display_name for i in items if i.quantity_received is None]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot export: missing quantity_received for: {', '.join(missing[:3])}"
                   + ("..." if len(missing) > 3 else ""),
        )

    xlsx_bytes = generate_xlsx(order, items)
    filename = f"1c_zakupka_{str(order_id)[:8]}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: Запустить все тесты**

```bash
docker compose exec backend pytest tests/ -v
```

Ожидаемый результат: все тесты PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/orders.py
git commit -m "feat: add DOCX and XLSX export endpoints for procurement orders"
```

---

## Task 4: Frontend — Download Buttons

**Files:**
- Modify: `frontend/src/app/(curator)/curator/queue/page.tsx`

- [ ] **Step 1: Добавить функцию скачивания в `queue/page.tsx`**

Прочитай файл. Добавь вспомогательную функцию `downloadFile` и кнопки для каждого заказа. Добавь после импортов:

```tsx
async function downloadFile(url: string, filename: string) {
  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}` },
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Ошибка скачивания" }))
    throw new Error(err.detail)
  }
  const blob = await resp.blob()
  const a = document.createElement("a")
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}
```

Добавь кнопки в карточку элемента (после кнопки "Назначить"):

```tsx
<div className="flex gap-1 mt-1">
  <Button
    size="sm"
    variant="outline"
    onClick={() =>
      downloadFile(
        `/api/orders/${item.order_id}/export/docx`,
        `zakupka_${item.order_id.slice(0, 8)}.docx`
      ).catch((e) => setError(e.message))
    }
  >
    Скачать DOCX
  </Button>
  <Button
    size="sm"
    variant="outline"
    onClick={() =>
      downloadFile(
        `/api/orders/${item.order_id}/export/xlsx`,
        `1c_${item.order_id.slice(0, 8)}.xlsx`
      ).catch((e) => setError(e.message))
    }
  >
    Экспорт 1C
  </Button>
</div>
```

**Примечание:** URL `/api/orders/...` должен проксироваться на бэкенд через `next.config.js`. Проверь что там настроен `rewrites` или `proxy`. Если нет — используй полный URL бэкенда через `process.env.NEXT_PUBLIC_API_URL`.

- [ ] **Step 2: TypeScript check**

```bash
cd "/home/danil/Рабочий стол/supplyflow/frontend" && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(curator)/curator/queue/page.tsx"
git commit -m "feat: add DOCX and XLSX download buttons to curator queue"
```

---

## Task 5: Final Verification

- [ ] **Step 1: Полный backend тест**

```bash
docker compose exec backend pytest tests/ -v
```

- [ ] **Step 2: TypeScript check**

```bash
cd "/home/danil/Рабочий стол/supplyflow/frontend" && npx tsc --noEmit
```

- [ ] **Step 3: Проверить export эндпоинты**

```bash
# Должны вернуть 401 (не 404)
curl -s -o /dev/null -w "%{http_code}" \
  "http://localhost:8000/orders/00000000-0000-0000-0000-000000000000/export/docx"
# Ожидаемый: 401
```

- [ ] **Step 4: Финальный commit**

```bash
git add -A
git commit -m "feat: procurement P3 complete — DOCX/XLSX generation and download"
```
