import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderTemplate(Base):
    __tablename__ = "order_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    restaurant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("restaurants.id"))
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    items: Mapped[list["OrderTemplateItem"]] = relationship(
        "OrderTemplateItem", back_populates="template", lazy="noload"
    )


class OrderTemplateItem(Base):
    __tablename__ = "order_template_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_templates.id", ondelete="CASCADE"))
    catalog_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("catalog_items.id"))
    quantity: Mapped[float] = mapped_column(Float)
    variant: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    template: Mapped["OrderTemplate"] = relationship(
        "OrderTemplate", back_populates="items", lazy="noload"
    )
