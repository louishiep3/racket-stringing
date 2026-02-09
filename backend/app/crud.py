# trigger commit

from __future__ import annotations

import secrets
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from . import models, schemas


# -----------------------
# token generator
# -----------------------
def _new_token(nbytes: int = 4) -> str:
    # 8 hex chars, upper
    return secrets.token_hex(nbytes).upper()


def _cycle_status(st: models.ItemStatus) -> models.ItemStatus:
    order = [
        models.ItemStatus.RECEIVED,
        models.ItemStatus.WORKING,
        models.ItemStatus.DONE,
        models.ItemStatus.PICKED_UP,
    ]
    i = order.index(st) if st in order else 0
    return order[(i + 1) % len(order)]


# =========================
# Customer
# =========================
def create_customer(db: Session, customer: schemas.CustomerCreate) -> models.Customer:
    obj = models.Customer(
        name=customer.name.strip(),
        phone=customer.phone.strip(),
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
    並回傳 OrderItem（Swagger 就能看到 token）
    """
    # 先建立 order
    od = models.Order(customer_id=order.customer_id)
    db.add(od)
    db.flush()  # 取得 od.id（不 commit）

    # 產生不重複 token（有 unique constraint，所以用 retry 保險）
    token = _new_token()
    for _ in range(5):
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

    # promised_done_time：如果你要固定 +3 小時，可改成 datetime.utcnow() + timedelta(hours=3)
    item = models.OrderItem(
        order_id=od.id,
        token=token,
        string_type=order.string_type.strip(),
        tension_main=int(order.tension_main),
        tension_cross=int(order.tension_cross),
        promised_done_time=datetime.utcnow(),  # 預設現在時間（可自行改）
        status=models.ItemStatus.RECEIVED,
        completed_at=None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item_status(db: Session, item_id: int, status: str) -> Optional[models.OrderItem]:
    obj = db.query(models.OrderItem).filter(models.OrderItem.id == item_id).first()
    if not obj:
        return None

    s = (status or "").upper().strip()
    try:
        obj.status = models.ItemStatus(s)
    except Exception:
        # 不合法狀態就不改
        return None

    if obj.status == models.ItemStatus.DONE and obj.completed_at is None:
        obj.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(obj)
    return obj


def update_promised_done_time(db: Session, item_id: int, dt: datetime) -> Optional[models.OrderItem]:
    obj = db.query(models.OrderItem).filter(models.OrderItem.id == item_id).first()
    if not obj:
        return None
    obj.promised_done_time = dt
    db.commit()
    db.refresh(obj)
    return obj


# =========================
# Track / Public
# =========================
def get_item_by_token(db: Session, token: str) -> Optional[Dict[str, Any]]:
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

    # done_time：你 UI 會顯示「穿線時間」
    # 這裡優先用 completed_at（DONE 時會填），沒有就用 promised_done_time
    done_dt = obj.completed_at or obj.promised_done_time
    done_time = ""
    if done_dt:
        done_time = done_dt.strftime("%Y-%m-%d %H:%M")

    return {
        # 你 main.py /public 用的是 name
        "name": c.name,
        "string_type": obj.string_type,
        "tension_main": obj.tension_main,
        "tension_cross": obj.tension_cross,
        "done_time": done_time,

        # staff_toggle page 用到 customer_name_raw
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
# Admin
# =========================
def _item_to_admin_dict(obj: models.OrderItem) -> Dict[str, Any]:
    c = obj.order.customer if obj.order else None
    return {
        "id": obj.id,
        "token": obj.token,
        "status": obj.status.value if hasattr(obj.status, "value") else str(obj.status),
        "string_type": obj.string_type,
        "tension_main": obj.tension_main,
        "tension_cross": obj.tension_cross,
        "promised_done_time": obj.promised_done_time.isoformat() if obj.promised_done_time else "",
        "completed_at": obj.completed_at.isoformat() if obj.completed_at else "",
        "customer_name": (c.name if c else ""),
        "customer_phone": (c.phone if c else ""),
    }


def admin_list_items_by_date(db: Session, day: date) -> List[Dict[str, Any]]:
    # 以 promised_done_time 的日期作為「當日」
    q = (
        db.query(models.OrderItem)
        .options(joinedload(models.OrderItem.order).joinedload(models.Order.customer))
        .filter(func.date(models.OrderItem.promised_done_time) == day)
        .order_by(models.OrderItem.promised_done_time.asc())
    )
    items = q.all()
    return [_item_to_admin_dict(x) for x in items]


def admin_summary_by_date(db, day):

    # ---- 總數 ----
    total = db.query(func.count(models.OrderItem.id))\
        .filter(func.date(models.OrderItem.promised_done_time) == day)\
        .scalar()

    # ---- 狀態統計 ----
    rows = db.query(
        models.OrderItem.status,
        func.count(models.OrderItem.id)
    ).filter(
        func.date(models.OrderItem.promised_done_time) == day
    ).group_by(
        models.OrderItem.status
    ).all()

    by_status = {r[0].name if hasattr(r[0], "name") else str(r[0]): r[1] for r in rows}

    # ---- 每小時統計（⭐ 修正重點）----
    hour_rows = db.query(
        func.extract("hour", models.OrderItem.promised_done_time).label("h"),
        func.count(models.OrderItem.id)
    ).filter(
        func.date(models.OrderItem.promised_done_time) == day
    ).group_by("h").all()

    by_hour = {
        f"{int(r[0]):02d}": r[1]
        for r in hour_rows if r[0] is not None
    }

    return {
        "total": total or 0,
        "by_status": by_status,
        "by_hour": by_hour
    }

def admin_search(db: Session, q: str) -> List[Dict[str, Any]]:
    kw = (q or "").strip()
    if not kw:
        return []

    items = (
        db.query(models.OrderItem)
        .options(joinedload(models.OrderItem.order).joinedload(models.Order.customer))
        .join(models.Order, models.OrderItem.order_id == models.Order.id)
        .join(models.Customer, models.Order.customer_id == models.Customer.id)
        .filter(
            or_(
                models.OrderItem.token.ilike(f"%{kw}%"),
                models.Customer.name.ilike(f"%{kw}%"),
                models.Customer.phone.ilike(f"%{kw}%"),
            )
        )
        .order_by(models.OrderItem.promised_done_time.desc())
        .limit(200)
        .all()
    )

    return [_item_to_admin_dict(x) for x in items]
