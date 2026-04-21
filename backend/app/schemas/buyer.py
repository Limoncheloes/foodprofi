import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class BuyerItemRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    display_name: str
    quantity_ordered: float
    quantity_received: float | None
    unit: str
    restaurant_name: str
    order_date: datetime

    model_config = {"from_attributes": True}


class MarkPurchasedRequest(BaseModel):
    quantity_received: float

    @field_validator("quantity_received")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("quantity_received must be positive")
        return v
