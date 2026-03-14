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
    name = Column(String)
    phone = Column(String)

    orders = relationship("Order", back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)

    customer_id = Column(Integer, ForeignKey("customers.id"))

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)

    order_id = Column(Integer, ForeignKey("orders.id"))

    token = Column(String, unique=True, index=True)

    # 新增訂單編號
    order_no = Column(String, index=True)

    string_type = Column(String)

    tension_main = Column(Integer)
    tension_cross = Column(Integer)

    status = Column(Enum(ItemStatus), default=ItemStatus.RECEIVED)

    promised_done_time = Column(DateTime)

    completed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="items")
