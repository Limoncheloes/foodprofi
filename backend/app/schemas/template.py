import uuid
from datetime import datetime
from pydantic import BaseModel


class TemplateItemCreate(BaseModel):
    catalog_item_id: uuid.UUID
    quantity: float
    variant: str | None = None
    note: str | None = None


class TemplateCreate(BaseModel):
    name: str
    restaurant_id: uuid.UUID
    items: list[TemplateItemCreate]


class TemplateItemRead(BaseModel):
    id: uuid.UUID
    catalog_item_id: uuid.UUID
    quantity: float
    variant: str | None
    note: str | None

    model_config = {"from_attributes": True}


class TemplateRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    restaurant_id: uuid.UUID
    name: str
    created_at: datetime
    items: list[TemplateItemRead] = []

    model_config = {"from_attributes": True}
