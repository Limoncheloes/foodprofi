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
