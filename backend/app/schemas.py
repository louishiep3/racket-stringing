from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    name: str
    phone: str


class CustomerOut(BaseModel):
    id: int
    name: str
    phone: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    customer_id: int
    string_type: str
    tension_main: int
    tension_cross: int


class ItemOut(BaseModel):
    id: int
    token: str
    order_no: Optional[str] = None
    status: str
    string_type: str
    tension_main: int
    tension_cross: int
    promised_done_time: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AdminCreateOneIn(BaseModel):
    name: str
    phone: str
    string_type: str
    tension_main: int
    tension_cross: int


class AdminCreateOneOut(BaseModel):
    customer_id: int
    item_id: int
    token: str
    order_no: str


class AdminSummaryOut(BaseModel):
    total: int = 0
    by_status: Dict[str, int] = {}
    by_hour: Dict[str, int] = {}
