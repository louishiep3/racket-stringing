# trigger commit
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session, joinedload

from . import models, schemas


# -----------------------
# token generator
# -----------------------
def _new_token(nbytes: int = 3) -> str:
    # 6 hex chars, upper (例如 5CYYMW)
    return secrets.token_hex(nbytes).upper()


def _cycle_status(st: models.ItemStatus) -> models.ItemStatus:
    # 依你需求：掃一次固定變 WORKING / DONE
    # 這裡用 2 狀態循環：RECEIVED -> WORKING -> DONE -> WORKING -> DONE...
    if st == models.ItemStatus.RECEIVED:
        return models.ItemStatus.WORKING
    if st == models.ItemStatus.WORKING:
        return models.ItemStatus.DONE
    if st == models.ItemStatus.DONE:
        return models.ItemStatus.WORKING
    if st == models.ItemStatus.PICKED_UP:
        return models.ItemStatus.WORKING
    return models.ItemStatus.WORKING


# =========================
# Customer
# =========================
def create_customer(db: Session, customer: schemas.CustomerCreate) -> models.Customer:
    obj = models.Customer(
        name=(customer.name or "").strip(),
        phone=(customer.phone or "").strip(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# =========================
# Order / Item
# =========================
def create_order(db: Session, order: schemas.OrderCreate) -> models.OrderItem:
    """
    建立一張 Order + 一筆 OrderItem（含 token）
    """
    od = models.Order(customer_id=int(order.customer_id))
    db.add(od)
    db.flush()  # 取得 od.id（不 commit）

    # 產生不重複 token（unique constraint + retry）
    token = _new_token()
    for _ in range(10):
        exists = (
            db.query(models.OrderItem.id)
            .filter(models.OrderItem.token == token)
            .first()
        )
        if not exists:
            break
        token = _new_token()
    else:
        raise RuntimeError("failed to generate unique token")

    item = models.OrderItem(
        order_id=od.id,
        token=token,
        string_type=(order.string_type or "").strip(),
        tension_main=int(order.tension_main),
        tension_cross=int(order.tension_cross),
        promised_done_time=datetime.utcnow(),
        status=models.ItemStatus.RECEIVED,
        completed_at=None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# =========================
# Public / Track
# =========================
def get_item_by_token(db: Session, token: str) -> Optional[Dict[str, Any]]:
    """
    給 /public/{token} 用：
    回傳客人頁需要的欄位（name, string_type, tension_main, tension_cross, done_time）
    以及一些後台/店員可能會用到的資訊（status, promised_done_time, completed_at...）
    """
    tok = (token or "").strip()

    obj: Optional[models.OrderItem] = (
        db.query(models.OrderItem)
        .options(joinedload(models.OrderItem.order).joinedload(models.Order.customer))
        .filter(models.OrderItem.token == tok)
        .first()
    )
    if not obj or not obj.order or not obj.order.customer:
        return None

    c = obj.order.customer

    done_dt = obj.completed_at or obj.promised_done_time
    done_time = done_dt.strftime("%Y-%m-%d %H:%M") if done_dt else ""

    return {
        "name": c.name,
        "string_type": obj.string_type,
        "tension_main": obj.tension_main,
        "tension_cross": obj.tension_cross,
        "done_time": done_time,

        # 下面是額外資訊（不一定每個 endpoint 都用到，但留著不會壞）
        "customer_name_raw": c.name,
        "customer_phone": c.phone,
        "token": obj.token,
        "status": obj.status.value if hasattr(obj.status, "value") else str(obj.status),
        "promised_done_time": obj.promised_done_time.isoformat() if obj.promised_done_time else "",
        "completed_at": obj.completed_at.isoformat() if obj.completed_at else "",
        "id": obj.id,
    }


# =========================
# Staff toggle
# =========================
def staff_toggle_status_by_token(db: Session, token: str) -> Optional[models.OrderItem]:
    tok = (token or "").strip()
    obj = db.query(models.OrderItem).filter(models.OrderItem.token == tok).first()
    if not obj:
        return None

    obj.status = _cycle_status(obj.status)

    if obj.status == models.ItemStatus.DONE and obj.completed_at is None:
        obj.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(obj)
    return obj


# =========================
# Admin create_one
# =========================
def admin_create_one(db: Session, payload: schemas.AdminCreateOneIn) -> Dict[str, Any]:
    """
    給 /api/admin/create_one 用：
    一次建立 customer + order(item) 並回傳 token
    """
    # 1) customer
    customer = models.Customer(
        name=(payload.name or "").strip(),
        phone=(payload.phone or "").strip(),
    )
    db.add(customer)
    db.flush()

    # 2) order
    od = models.Order(customer_id=customer.id)
    db.add(od)
    db.flush()

    # 3) item
    token = _new_token()
    for _ in range(10):
        exists = (
            db.query(models.OrderItem.id)
            .filter(models.OrderItem.token == token)
            .first()
        )
        if not exists:
            break
        token = _new_token()
    else:
        raise RuntimeError("failed to generate unique token")

    item = models.OrderItem(
        order_id=od.id,
        token=token,
        string_type=(payload.string_type or "").strip(),
        tension_main=int(payload.tension_main),
        tension_cross=int(payload.tension_cross),
        promised_done_time=datetime.utcnow(),
        status=models.ItemStatus.RECEIVED,
        completed_at=None,
    )
    db.add(item)

    db.commit()
    db.refresh(customer)
    db.refresh(item)

    return {
        "customer_id": customer.id,
        "item_id": item.id,
        "token": item.token,
    }
