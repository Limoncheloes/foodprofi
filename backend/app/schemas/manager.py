import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.order import OrderStatus
from app.schemas.order import OrderItemRead


class StaffCreate(BaseModel):
    phone: str = Field(min_length=7, max_length=20, pattern=r"^\+\d{6,19}$")
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    role: Literal["cook", "manager"]


class StaffRead(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    role: str
    restaurant_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class StaffCreateResponse(StaffRead):
    access_token: str
    refresh_token: str


class ManagerOrderRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    restaurant_id: uuid.UUID
    status: OrderStatus
    is_urgent: bool
    deadline: datetime | None
    created_at: datetime
    items: list[OrderItemRead]


class RestaurantSettingsRead(BaseModel):
    restaurant_id: uuid.UUID
    requires_approval: bool
