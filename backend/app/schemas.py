from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ==============
# Customer
# ==============
class CustomerCreate(BaseModel):
    name: str
    phone: str


class CustomerOut(BaseModel):
    id: int
    name: str
    phone: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==============
# Order / Item
# ==============
class OrderCreate(BaseModel):
    customer_id: int
    string_type: str
    tension_main: int
    tension_cross: int


class ItemOut(BaseModel):
    id: int
    customer_id: int
    string_type: str
    tension_main: int
    tension_cross: int
    token: str                    # ✅ 這個就是你要看到的
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    promised_done_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
