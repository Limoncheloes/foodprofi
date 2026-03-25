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

    model_config = {"from_attributes": True}
