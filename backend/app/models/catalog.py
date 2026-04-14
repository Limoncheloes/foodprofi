import uuid
from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UnitType(str, enum.Enum):
    kg = "kg"
    pcs = "pcs"
    liters = "liters"
    packs = "packs"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    default_buyer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String(255))
    unit: Mapped[UnitType] = mapped_column(Enum(UnitType))
    variants: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
