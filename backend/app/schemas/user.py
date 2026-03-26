import uuid

from pydantic import BaseModel, Field

from app.models.user import UserRole


class UserRead(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    role: UserRole
    restaurant_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class AdminCreateUserRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=20, pattern=r"^\+\d{6,19}$")
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    role: UserRole
    restaurant_id: uuid.UUID | None = None


class CreateUserResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead
