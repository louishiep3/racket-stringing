import enum
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey, Enum, Text

from .db import Base


class ItemStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    WORKING = "WORKING"
    DONE = "DONE"
    PICKED_UP = "PICKED_UP"


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    orders = relationship("Order", back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))

    # ✅ 追蹤碼 token（你 DB 已經加了 not null + unique index）
    token: Mapped[str] = mapped_column(String(40), unique=True, index=True)

    string_type: Mapped[str] = mapped_column(String(80))
    tension_main: Mapped[int] = mapped_column(Integer)
    tension_cross: Mapped[int] = mapped_column(Integer)

    promised_done_time: Mapped[datetime] = mapped_column(DateTime)

    # ✅ 完成時間（DONE 時會填）
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.RECEIVED)

    order = relationship("Order", back_populates="items")
