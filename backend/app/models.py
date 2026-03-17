from datetime import datetime
import enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from .db import Base


class ItemStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    WORKING = "WORKING"
    DONE = "DONE"
    PICKED_UP = "PICKED_UP"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    orders = relationship(
        "Order",
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    customer = relationship("Customer", back_populates="orders")
    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)

    token = Column(String, unique=True, index=True, nullable=False)
    order_no = Column(String, index=True, nullable=True)

    string_type = Column(String, nullable=False)
    tension_main = Column(Integer, nullable=False)
    tension_cross = Column(Integer, nullable=False)

    status = Column(
        Enum(ItemStatus, native_enum=False),
        default=ItemStatus.RECEIVED,
        nullable=False,
    )

    promised_done_time = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    note = Column(String, nullable=True)

    order = relationship("Order", back_populates="items")
