import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum, ForeignKey,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Any

from app.database import Base


class ProcurementItemStatus(str, enum.Enum):
    pending_curator = "pending_curator"
    assigned = "assigned"
    purchased = "purchased"
    not_found = "not_found"
    substituted = "substituted"


class ProcurementItem(Base):
    __tablename__ = "procurement_items"
    __table_args__ = (
        CheckConstraint(
            "catalog_item_id IS NOT NULL OR raw_name IS NOT NULL",
            name="ck_procurement_item_has_name",
        ),
        CheckConstraint("quantity_ordered > 0", name="ck_procurement_item_qty_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    catalog_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("catalog_items.id"), nullable=True
    )
    raw_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity_ordered: Mapped[float] = mapped_column(Numeric(10, 3))
    quantity_received: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[str] = mapped_column(String(50))
    status: Mapped[ProcurementItemStatus] = mapped_column(
        Enum(ProcurementItemStatus, name="procurementitemstatus"),
        default=ProcurementItemStatus.pending_curator,
    )
    buyer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    curator_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    substitution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_catalog_item: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    catalog_item: Mapped[Any] = relationship("CatalogItem", foreign_keys=[catalog_item_id], lazy="noload")
    buyer: Mapped[Any] = relationship("User", foreign_keys=[buyer_id], lazy="noload")
    category: Mapped[Any] = relationship("Category", foreign_keys=[category_id], lazy="noload")

    @property
    def display_name(self) -> str:
        if self.catalog_item:
            return self.catalog_item.name
        return self.raw_name or ""


class RoutingRule(Base):
    __tablename__ = "routing_rules"
    __table_args__ = (
        UniqueConstraint("keyword", name="uq_routing_rules_keyword"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    keyword: Mapped[str] = mapped_column(String(255))
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    created_by_curator: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    buyer: Mapped[Any] = relationship("User", foreign_keys=[buyer_id], lazy="noload")
