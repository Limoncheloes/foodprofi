import uuid
from app.models.catalog import UnitType
from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    sort_order: int = 0


class CategoryRead(BaseModel):
    id: uuid.UUID
    name: str
    sort_order: int
    default_buyer_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class CatalogItemCreate(BaseModel):
    category_id: uuid.UUID
    name: str
    unit: UnitType
    variants: list[str] = []


class CatalogItemUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    variants: list[str] | None = None


class CatalogItemRead(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    unit: UnitType
    variants: list[str]
    is_active: bool

    model_config = {"from_attributes": True}
