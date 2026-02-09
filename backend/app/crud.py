from __future__ import annotations

import secrets
from datetime import datetime, date
from sqlalchemy.orm import Session

from . import models, schemas


def gen_token(n: int = 8) -> str:
    # 8碼大寫 HEX，例如 A1B2C3D4
    return secrets.token_hex(n // 2).upper()


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
    token = gen_token(8)

    obj = models.Item(
        customer_id=order.customer_id,
        string_type=order.string_type,
        tension_main=order.tension_main,
        tension_cross=order.tension_cross,
        token=token,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
