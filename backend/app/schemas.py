from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ItemStatus(str, Enum):
    RECEIVED = "RECEIVED"
    WORKING = "WORKING"
    DONE = "DONE"
    PICKED_UP = "PICKED_UP"


class CustomerCreate(BaseModel):
    name: str
    phone: str


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    created_at: datetime


class OrderItemCreate(BaseModel):
    string_type: str
    tension_main: int
    tension_cross: int
    promised_done_time: datetime


class OrderCreate(BaseModel):
    customer_id: int
    note: str | None = None
    items: list[OrderItemCreate] = Field(default_factory=list)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    token: str
    string_type: str
    tension_main: int
    tension_cross: int
    status: ItemStatus
    promised_done_time: datetime
    completed_at: datetime | None = None


class OrderCreateResult(BaseModel):
    order_id: int
    items: list[OrderItemOut]


class TrackOut(BaseModel):
    name: str
    string_type: str
    tension_main: int
    tension_cross: int
    status: str
    done_time: str | None
