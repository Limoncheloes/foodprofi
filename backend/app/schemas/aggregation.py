import uuid
from datetime import date
from pydantic import BaseModel, Field


class RestaurantNeed(BaseModel):
    restaurant_id: uuid.UUID
    quantity: float
    variant: str | None = None


class AggregationItemRead(BaseModel):
    catalog_item_id: uuid.UUID
    name: str
    unit: str
    total_needed: float
    in_stock: float
    to_buy: float
    restaurants: list[RestaurantNeed]


class AggregationCategoryRead(BaseModel):
    category_id: uuid.UUID
    category_name: str
    items: list[AggregationItemRead]


class AggregationSummary(BaseModel):
    date: date
    categories: list[AggregationCategoryRead]


class PurchaseItem(BaseModel):
    catalog_item_id: uuid.UUID
    quantity_bought: float = Field(gt=0)
    price: float | None = Field(default=None, ge=0)


class MarkPurchasedRequest(BaseModel):
    date: date
    purchases: list[PurchaseItem]


class MarkPurchasedResponse(BaseModel):
    updated_orders: int
    purchases_recorded: int
