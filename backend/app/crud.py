# trigger commit
from __future__ import annotations

import secrets
from datetime import datetime, date
from typing import Any, Dict, Optional, List

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

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


def _parse_status(status: str) -> models.ItemStatus:
    s = (status or "").strip().upper()
    # 允許 "ItemStatus.DONE" 這種也能進來
    s = s.replace("ITEMSTATUS.", "")
    try:
        return models.ItemStatus[s]
    except Exception:
        raise ValueError(f"Invalid status: {status}")


def _status_str(st: Any) -> str:
    # Enum / string 都吃
    if hasattr(st, "value"):
        return st.value
    s = str(st)
    return s.replace("ItemStatus.", "")


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
        promised_done_time=datetime.utcnow(),  # 預設先給現在時間；之後可用 admin patch 改
        status=models.ItemStatus.RECEIVED,
        completed_at=None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_item_by_id(db: Session, item_id: int) -> Optional[models.OrderItem]:
    return db.query(models.OrderItem).filter(models.OrderItem.id == int(item_id)).first()


# =========================
# Public / Track
# =========================
def get_item_by_token(db: Session, token: str) -> Optional[Dict[str, Any]]:
    """
    給 /public/{token} 用：
    回傳客人頁需要的欄位（name, string_type, tension_main, tension_cross, done_time）
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
        promised_done_time=datetime.utcnow(),  # 預設，APP 會再 PATCH 改成「預約時間」
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


# =========================
# ✅ Admin：更新狀態 / 更新預約時間
# =========================
def update_item_status(db: Session, item_id: int, status: str) -> Optional[models.OrderItem]:
    obj = db.query(models.OrderItem).filter(models.OrderItem.id == int(item_id)).first()
    if not obj:
        return None

    try:
        st = _parse_status(status)
    except ValueError:
        return None

    obj.status = st

    # DONE 時補 completed_at（你要的話）
    if st == models.ItemStatus.DONE and obj.completed_at is None:
        obj.completed_at = datetime.utcnow()

    # 非 DONE 就清掉 completed_at（避免狀態來回）
    if st != models.ItemStatus.DONE and obj.completed_at is not None:
        obj.completed_at = None

    db.commit()
    db.refresh(obj)
    return obj


def update_promised_done_time(db: Session, item_id: int, promised: datetime) -> Optional[models.OrderItem]:
    obj = db.query(models.OrderItem).filter(models.OrderItem.id == int(item_id)).first()
    if not obj:
        return None
    obj.promised_done_time = promised
    db.commit()
    db.refresh(obj)
    return obj


# =========================
# ✅ Admin：列表 / 搜尋 / 統計
# =========================
def _to_admin_item(obj: models.OrderItem) -> Dict[str, Any]:
    """
    回傳格式要對上 APP 的 AdminItem data class：
    id/token/status/string_type/tension_main/tension_cross/promised_done_time/customer_name/customer_phone
    """
    cust = None
    if obj.order and obj.order.customer:
        cust = obj.order.customer

    promised = obj.promised_done_time.strftime("%Y-%m-%d %H:%M") if obj.promised_done_time else None

    return {
        "id": obj.id,
        "token": obj.token,
        "status": _status_str(obj.status),
        "string_type": obj.string_type,
        "tension_main": int(obj.tension_main),
        "tension_cross": int(obj.tension_cross),
        "promised_done_time": promised,
        "customer_name": (cust.name if cust else None),
        "customer_phone": (cust.phone if cust else None),
    }


def admin_list_items_by_date(db: Session, day: date) -> List[Dict[str, Any]]:
    """
    給 /api/admin/items?date=YYYY-MM-DD
    用 promised_done_time 的日期做篩選
    """
    q = (
        db.query(models.OrderItem)
        .options(joinedload(models.OrderItem.order).joinedload(models.Order.customer))
        .filter(func.date(models.OrderItem.promised_done_time) == day)
        .order_by(models.OrderItem.id.desc())
    )

    return [_to_admin_item(x) for x in q.all()]


def admin_search(db: Session, q: str) -> List[Dict[str, Any]]:
    """
    給 /api/admin/search?q=...
    token / 姓名 / 電話 模糊搜尋
    """
    kw = (q or "").strip()
    if not kw:
        return []

    like = f"%{kw}%"

    rows = (
        db.query(models.OrderItem)
        .join(models.Order, models.OrderItem.order_id == models.Order.id)
        .join(models.Customer, models.Order.customer_id == models.Customer.id)
        .options(joinedload(models.OrderItem.order).joinedload(models.Order.customer))
        .filter(
            or_(
                models.OrderItem.token.ilike(like),
                models.Customer.name.ilike(like),
                models.Customer.phone.ilike(like),
            )
        )
        .order_by(models.OrderItem.id.desc())
        .limit(200)
        .all()
    )

    return [_to_admin_item(x) for x in rows]


def admin_summary_by_date(db: Session, day: date) -> Dict[str, Any]:
    """
    給 /api/admin/summary?date=YYYY-MM-DD
    回傳：
    {
      "total": int,
      "by_status": {"RECEIVED": 1, ...},
      "by_hour": {"09": 3, "10": 2, ...}
    }
    """
    base = (
        db.query(models.OrderItem)
        .filter(func.date(models.OrderItem.promised_done_time) == day)
    )

    total = base.count()

    # by_status
    st_rows = (
        db.query(models.OrderItem.status, func.count(models.OrderItem.id))
        .filter(func.date(models.OrderItem.promised_done_time) == day)
        .group_by(models.OrderItem.status)
        .all()
    )
    by_status: Dict[str, int] = {}
    for st, cnt in st_rows:
        by_status[_status_str(st)] = int(cnt)

    # by_hour（用 promised_done_time 的小時）
    # SQLite 用 strftime('%H', dt)，Postgres 可用 extract(hour from dt)
    # 這裡用 strftime，Render 多半是 SQLite / Postgres 皆可能，盡量兼容：
    try:
        hour_key = func.strftime("%H", models.OrderItem.promised_done_time)
        hr_rows = (
            db.query(hour_key.label("h"), func.count(models.OrderItem.id))
            .filter(func.date(models.OrderItem.promised_done_time) == day)
            .group_by("h")
            .all()
        )
        by_hour = {str(h): int(cnt) for h, cnt in hr_rows if h is not None}
    except Exception:
        # fallback：用 Python 分組（資料量通常不大）
        rows = (
            db.query(models.OrderItem.promised_done_time)
            .filter(func.date(models.OrderItem.promised_done_time) == day)
            .all()
        )
        by_hour: Dict[str, int] = {}
        for (dt,) in rows:
            if not dt:
                continue
            hh = f"{dt.hour:02d}"
            by_hour[hh] = by_hour.get(hh, 0) + 1

    return {
        "total": int(total),
        "by_status": by_status,
        "by_hour": by_hour,
    }
