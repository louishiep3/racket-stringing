from __future__ import annotations

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

    id = Column(Integer, primary_key=True, index=True)

    order_id = Column(Integer, ForeignKey("orders.id"))

    token = Column(String, unique=True, index=True)

    # 新增這行
    order_no = Column(String, index=True)

    string_type = Column(String)
    tension_main = Column(Integer)
    tension_cross = Column(Integer)

    status = Column(Enum(ItemStatus), default=ItemStatus.RECEIVED)

    promised_done_time = Column(DateTime)

    completed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="items")
