import uuid
from datetime import datetime

from pydantic import BaseModel


class AssignRequest(BaseModel):
    item_id: uuid.UUID
    buyer_id: uuid.UUID
    category_id: uuid.UUID | None = None
    save_rule: bool = False   # if True → also create/update RoutingRule


class RuleCreate(BaseModel):
    keyword: str
    buyer_id: uuid.UUID
    category_id: uuid.UUID | None = None


class RuleUpdate(BaseModel):
    buyer_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None


class RuleRead(BaseModel):
    id: uuid.UUID
    keyword: str
    buyer_id: uuid.UUID
    buyer_name: str
    category_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CuratorStats(BaseModel):
    pending_count: int


class PendingItemRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    display_name: str
    raw_name: str | None
    quantity_ordered: float
    unit: str
    is_catalog_item: bool
    restaurant_name: str
    created_at: datetime

    model_config = {"from_attributes": True}
