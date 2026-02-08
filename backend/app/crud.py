from __future__ import annotations

import secrets
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from . import models, schemas


def _gen_token(n: int = 6) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def create_customer(db: Session, customer: schemas.CustomerCreate):
    db_customer = models.Customer(
        name=customer.name,
        phone=customer.phone,
    )
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer


def create_order(db: Session, order: schemas.OrderCreate):
    db_order = models.Order(
        customer_id=order.customer_id,
        note=order.note,
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    # 建 items（含 token）
    for item in order.items:
        token = _gen_token(6)
        db_item = models.OrderItem(
            order_id=db_order.id,
            token=token,
            string_type=item.string_type,
            tension_main=item.tension_main,
            tension_cross=item.tension_cross,
            promised_done_time=item.promised_done_time,
            status=models.ItemStatus.RECEIVED,
        )
        db.add(db_item)

    db.commit()
    db.refresh(db_order)
    return db_order


def update_item_status(db: Session, item_id: int, status: str):
    item = db.query(models.OrderItem).filter(models.OrderItem.id == item_id).first()
    if not item:
        return None

    s = (status or "").strip().upper()
    try:
        item.status = models.ItemStatus(s)
    except Exception:
        return None

    if hasattr(item, "completed_at"):
        if item.status == models.ItemStatus.DONE and item.completed_at is None:
            item.completed_at = datetime.utcnow()
        if item.status != models.ItemStatus.DONE and item.completed_at is not None:
            item.completed_at = None

    db.commit()
    db.refresh(item)
    return item


def get_item_by_token(db: Session, token: str):
    t = (token or "").strip().upper()

    row = (
        db.query(
            models.OrderItem.id.label("item_id"),
            models.OrderItem.token,
            models.OrderItem.string_type,
            models.OrderItem.tension_main,
            models.OrderItem.tension_cross,
            models.OrderItem.status,
            models.OrderItem.promised_done_time,
            models.Customer.name.label("customer_name"),
            models.Customer.phone.label("customer_phone"),
        )
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .join(models.Customer, models.Customer.id == models.Order.customer_id)
        .filter(models.OrderItem.token.ilike(t))
        .first()
    )

    if not row:
        return None

    def mask_name(name: str) -> str:
        if not name:
            return ""
        if len(name) <= 1:
            return name
        if len(name) == 2:
            return name[0] + "○"
        if len(name) == 3:
            return name[0] + "○" + name[-1]
        return name[0] + "○" * (len(name) - 2) + name[-1]

    done_time_str = (
        row.promised_done_time.strftime("%Y-%m-%d %H:%M")
        if row.promised_done_time
        else ""
    )

    status_str = row.status.value if hasattr(row.status, "value") else str(row.status)
    status_str = status_str.replace("ItemStatus.", "")

    return {
        "item_id": row.item_id,
        "token": row.token,
        "name": mask_name(row.customer_name),
        "customer_name_raw": row.customer_name or "",
        "customer_phone": row.customer_phone or "",
        "string_type": row.string_type or "",
        "tension_main": row.tension_main,
        "tension_cross": row.tension_cross,
        "status": status_str,
        "done_time": done_time_str,
        "promised_done_time": row.promised_done_time,
    }


# =====================
# ✅ 店員掃碼：用 token 直接切狀態
# =====================
def staff_toggle_status_by_token(db: Session, token: str):
    t = (token or "").strip().upper()
    item = db.query(models.OrderItem).filter(models.OrderItem.token.ilike(t)).first()
    if not item:
        return None

    cur = item.status.value if hasattr(item.status, "value") else str(item.status)
    cur = cur.replace("ItemStatus.", "").upper()

    # 狀態循環：你要「掃一下就切」
    nxt_map = {
        "RECEIVED": "WORKING",
        "WORKING": "DONE",
        "DONE": "PICKED_UP",
        "PICKED_UP": "RECEIVED",
    }
    nxt = nxt_map.get(cur, "WORKING")

    try:
        item.status = models.ItemStatus(nxt)
    except Exception:
        return None

    if hasattr(item, "completed_at"):
        if nxt == "DONE" and item.completed_at is None:
            item.completed_at = datetime.utcnow()
        if nxt != "DONE" and item.completed_at is not None:
            item.completed_at = None

    db.commit()
    db.refresh(item)

    return item


# =====================
# ✅ Admin 後台：summary / list / search（PostgreSQL 版）
# =====================
def _day_range(day: date):
    start = datetime(day.year, day.month, day.day, 0, 0, 0)
    end = start + timedelta(days=1)
    return start, end


def admin_summary_by_date(db: Session, day: date):
    start, end = _day_range(day)

    q = db.query(models.OrderItem).filter(
        and_(
            models.OrderItem.promised_done_time >= start,
            models.OrderItem.promised_done_time < end,
        )
    )

    total = q.count()

    # by_status
    rows = (
        db.query(models.OrderItem.status, func.count(models.OrderItem.id))
        .filter(
            and_(
                models.OrderItem.promised_done_time >= start,
                models.OrderItem.promised_done_time < end,
            )
        )
        .group_by(models.OrderItem.status)
        .all()
    )
    by_status = {}
    for st, cnt in rows:
        k = st.value if hasattr(st, "value") else str(st)
        k = k.replace("ItemStatus.", "")
        by_status[k] = int(cnt)

    # by_hour（Postgres：extract hour）
    rows2 = (
        db.query(func.extract("hour", models.OrderItem.promised_done_time).label("hh"), func.count(models.OrderItem.id))
        .filter(
            and_(
                models.OrderItem.promised_done_time >= start,
                models.OrderItem.promised_done_time < end,
            )
        )
        .group_by("hh")
        .order_by("hh")
        .all()
    )
    by_hour = {}
    for hh, cnt in rows2:
        by_hour[str(int(hh)).zfill(2)] = int(cnt)

    return {"total": total, "by_status": by_status, "by_hour": by_hour}


def admin_list_items_by_date(db: Session, day: date):
    start, end = _day_range(day)

    rows = (
        db.query(
            models.OrderItem.id,
            models.OrderItem.token,
            models.OrderItem.string_type,
            models.OrderItem.tension_main,
            models.OrderItem.tension_cross,
            models.OrderItem.status,
            models.OrderItem.promised_done_time,
            models.Customer.name.label("customer_name"),
            models.Customer.phone.label("customer_phone"),
        )
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .join(models.Customer, models.Customer.id == models.Order.customer_id)
        .filter(
            and_(
                models.OrderItem.promised_done_time >= start,
                models.OrderItem.promised_done_time < end,
            )
        )
        .order_by(models.OrderItem.promised_done_time.asc())
        .all()
    )

    out = []
    for r in rows:
        st = r.status.value if hasattr(r.status, "value") else str(r.status)
        st = st.replace("ItemStatus.", "")
        out.append(
            {
                "id": r.id,
                "token": r.token,
                "string_type": r.string_type,
                "tension_main": r.tension_main,
                "tension_cross": r.tension_cross,
                "status": st,
                "promised_done_time": r.promised_done_time.strftime("%Y-%m-%d %H:%M") if r.promised_done_time else "",
                "customer_name": r.customer_name or "",
                "customer_phone": r.customer_phone or "",
            }
        )
    return out


def admin_search(db: Session, q: str):
    kw = (q or "").strip()
    if not kw:
        return []

    rows = (
        db.query(
            models.OrderItem.id,
            models.OrderItem.token,
            models.OrderItem.string_type,
            models.OrderItem.tension_main,
            models.OrderItem.tension_cross,
            models.OrderItem.status,
            models.OrderItem.promised_done_time,
            models.Customer.name.label("customer_name"),
            models.Customer.phone.label("customer_phone"),
        )
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .join(models.Customer, models.Customer.id == models.Order.customer_id)
        .filter(
            or_(
                models.OrderItem.token.ilike(f"%{kw}%"),
                models.Customer.name.ilike(f"%{kw}%"),
                models.Customer.phone.ilike(f"%{kw}%"),
            )
        )
        .order_by(models.OrderItem.promised_done_time.desc().nullslast())
        .limit(200)
        .all()
    )

    out = []
    for r in rows:
        st = r.status.value if hasattr(r.status, "value") else str(r.status)
        st = st.replace("ItemStatus.", "")
        out.append(
            {
                "id": r.id,
                "token": r.token,
                "string_type": r.string_type,
                "tension_main": r.tension_main,
                "tension_cross": r.tension_cross,
                "status": st,
                "promised_done_time": r.promised_done_time.strftime("%Y-%m-%d %H:%M") if r.promised_done_time else "",
                "customer_name": r.customer_name or "",
                "customer_phone": r.customer_phone or "",
            }
        )
    return out


def update_promised_done_time(db: Session, item_id: int, dt: datetime):
    item = db.query(models.OrderItem).filter(models.OrderItem.id == item_id).first()
    if not item:
        return None
    item.promised_done_time = dt
    db.commit()
    db.refresh(item)
    return item
