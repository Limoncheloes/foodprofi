import uuid
from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserRole(str, enum.Enum):
    cook = "cook"
    buyer = "buyer"
    warehouse = "warehouse"
    driver = "driver"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    restaurant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("restaurants.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
