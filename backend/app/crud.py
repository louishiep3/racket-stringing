# trigger commit
from __future__ import annotations

import secrets
from datetime import datetime, date
from typing import Any, Dict, Optional, List

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, cast
from sqlalchemy.types import Date as SqlDate

from . import models, schemas


# -----------------------
# token generator
# -----------------------
def _new_token(nbytes: int = 3) -> str:
    # 6 hex chars, upper (例如 5CYYMW)
    return secrets.token_hex(nbytes).upper()


def _cycle_status(st: models.ItemStatus) -> models.ItemStatus:
    # 依你需求：掃一次固定變 WORKING / DONE
    # RECEIVED -> WORKING -> DONE -> WORKING -> DONE...
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
    s = s.replace("ITEMSTATUS.", "")
    try:
        return models.ItemStatus[s]
    except Exception:
        raise ValueError(f"Invalid status: {status}")


def _status_str(st: Any) -> str:
    if hasattr(st, "value"):
        return st.value
    s = str(st)
    return s.replace("ItemStatus.", "")


def _is_postgres(db: Session) -> bool:
    """
    判斷目前連線是否 Postgres
    """
    try:
        name = (db.get_bind().dialect.name or "").lower()
        return name.startswith("postgres")
    except Exception:
        return False


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


def get_item_by_id(db: Session, item_id: int) -> Optional[models.OrderItem]:
    return db.query(models.OrderItem).filter(models.OrderItem.id == int(item_id)).first()


# =========================
# Public / Track
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
    customer = models.Customer(
        name=(payload.name or "").strip(),
        phone=(payload.phone or "").strip(),
    )
    db.add(customer)
    db.flush()

    od = models.Order(customer_id=customer.id)
    db.add(od)
    db.flush()

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


# =========================
# Admin update
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

    if st == models.ItemStatus.DONE and obj.completed_at is None:
        obj.completed_at = datetime.utcnow()

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
# Admin list / search / summary
# =========================
def _to_admin_item(obj: models.OrderItem) -> Dict[str, Any]:
    cust = obj.order.customer if (obj.order and obj.order.customer) else None
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
    q = (
        db.query(models.OrderItem)
        .options(joinedload(models.OrderItem.order).joinedload(models.Order.customer))
        .filter(cast(models.OrderItem.promised_done_time, SqlDate) == day)
        .order_by(models.OrderItem.id.desc())
    )
    return [_to_admin_item(x) for x in q.all()]


def admin_search(db: Session, q: str) -> List[Dict[str, Any]]:
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
    # total
    total = (
        db.query(func.count(models.OrderItem.id))
        .filter(cast(models.OrderItem.promised_done_time, SqlDate) == day)
        .scalar()
        or 0
    )

    # by_status
    st_rows = (
        db.query(models.OrderItem.status, func.count(models.OrderItem.id))
        .filter(cast(models.OrderItem.promised_done_time, SqlDate) == day)
        .group_by(models.OrderItem.status)
        .all()
    )
    by_status: Dict[str, int] = { _status_str(st): int(cnt) for st, cnt in st_rows }

    # by_hour
    if _is_postgres(db):
        # ✅ Postgres：to_char(dt, 'HH24') -> "00"~"23"
        hr_rows = (
            db.query(
                func.to_char(models.OrderItem.promised_done_time, "HH24").label("h"),
                func.count(models.OrderItem.id),
            )
            .filter(cast(models.OrderItem.promised_done_time, SqlDate) == day)
            .group_by("h")
            .all()
        )
        by_hour: Dict[str, int] = { str(h): int(cnt) for h, cnt in hr_rows if h is not None }
    else:
        # ✅ SQLite / 其他：用 Python 分組（小量資料很快）
        rows = (
            db.query(models.OrderItem.promised_done_time)
            .filter(cast(models.OrderItem.promised_done_time, SqlDate) == day)
            .all()
        )
        by_hour = {}
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
