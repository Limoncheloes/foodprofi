import uuid

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=20)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=20, pattern=r"^\+\d{6,19}$")
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    restaurant_id: uuid.UUID | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
