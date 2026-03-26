import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.inventory import InventoryReason


class InventoryItemRead(BaseModel):
    catalog_item_id: uuid.UUID
    name: str
    unit: str
    quantity: float
    updated_at: datetime


class StockReceiveRequest(BaseModel):
    catalog_item_id: uuid.UUID
    quantity: float = Field(gt=0)
    note: str | None = Field(default=None, max_length=255)


class StockAdjustRequest(BaseModel):
    catalog_item_id: uuid.UUID
    quantity: float = Field(ge=0)
    note: str | None = Field(default=None, max_length=255)


class StockAdjustResponse(BaseModel):
    catalog_item_id: uuid.UUID
    previous_quantity: float
    new_quantity: float


class InventoryLogRead(BaseModel):
    id: uuid.UUID
    catalog_item_id: uuid.UUID
    item_name: str
    delta: float
    reason: InventoryReason
    user_name: str
    note: str | None
    created_at: datetime
