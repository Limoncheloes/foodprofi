import uuid

from pydantic import BaseModel

from app.models.user import UserRole


class UserRead(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    role: UserRole
    restaurant_id: uuid.UUID | None

    model_config = {"from_attributes": True}
