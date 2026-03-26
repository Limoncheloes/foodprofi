import uuid
from pydantic import BaseModel


class RestaurantCreate(BaseModel):
    name: str
    address: str
    contact_phone: str


class RestaurantRead(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    contact_phone: str
    is_active: bool
    requires_approval: bool

    model_config = {"from_attributes": True}


class RestaurantSettingsUpdate(BaseModel):
    requires_approval: bool
