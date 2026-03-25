import uuid
from datetime import datetime
from app.models.order import OrderStatus
from pydantic import BaseModel


class OrderItemCreate(BaseModel):
    catalog_item_id: uuid.UUID
    quantity: float
    variant: str | None = None
    note: str | None = None


class OrderItemRead(BaseModel):
    id: uuid.UUID
    catalog_item_id: uuid.UUID
    quantity: float
    variant: str | None
    note: str | None

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    restaurant_id: uuid.UUID
    is_urgent: bool = False
    deadline: datetime | None = None
    items: list[OrderItemCreate]


class OrderRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    restaurant_id: uuid.UUID
    status: OrderStatus
    is_urgent: bool
    deadline: datetime | None = None
    created_at: datetime
    items: list[OrderItemRead] = []

    model_config = {"from_attributes": True}
