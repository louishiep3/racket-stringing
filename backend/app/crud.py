from datetime import datetime
import random
import string

from sqlalchemy.orm import Session

from . import models, schemas


# =====================
# 工具：產生 6 碼 token
# =====================

def generate_token(db: Session) -> str:
    while True:
        token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        exists = db.query(models.OrderItem).filter_by(token=token).first()
        if not exists:
            return token


# =====================
# 基本 CRUD
# =====================

def create_customer(db: Session, customer: schemas.CustomerCreate):
    obj = models.Customer(
        name=customer.name,
        phone=customer.phone,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def create_order(db: Session, order: schemas.OrderCreate):
    token = generate_token(db)

    order_obj = models.Order(
        customer_id=order.customer_id,
    )
    db.add(order_obj)
    db.flush()

    item = models.OrderItem(
        order_id=order_obj.id,
        token=token,
        string_type=order.string_type,
        tension_main=order.tension_main,
        tension_cross=order.tension_cross,
        promised_done_time=datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# =====================
# ✅ Admin 一鍵新增
# =====================

def admin_create_one(db: Session, data: schemas.AdminCreateOneIn):
    # 建客人
    customer = models.Customer(
        name=data.name,
        phone=data.phone,
    )
    db.add(customer)
    db.flush()

    # 建訂單
    order = models.Order(
        customer_id=customer.id,
    )
    db.add(order)
    db.flush()

    # 建 item
    token = generate_token(db)

    item = models.OrderItem(
        order_id=order.id,
        token=token,
        string_type=data.string_type,
        tension_main=data.tension_main,
        tension_cross=data.tension_cross,
        promised_done_time=datetime.utcnow(),
    )
    db.add(item)

    db.commit()

    return {
        "customer_id": customer.id,
        "item_id": item.id,
        "token": token,
    }
