def _cycle_status(st: models.ItemStatus) -> models.ItemStatus:
    if st == models.ItemStatus.RECEIVED:
        return models.ItemStatus.WORKING
    if st == models.ItemStatus.WORKING:
        return models.ItemStatus.DONE
    if st == models.ItemStatus.DONE:
        return models.ItemStatus.PICKED_UP
    if st == models.ItemStatus.PICKED_UP:
        return models.ItemStatus.PICKED_UP
    return models.ItemStatus.WORKING


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
    promised = obj.promised_done_time.strftime("%Y-%m-%d %H:%M") if obj.promised_done_time else None

    return {
        "token": obj.token,
        "order_no": getattr(obj, "order_no", None),
        "status": _status_str(obj.status),
        "string_type": obj.string_type,
        "tension_main": int(obj.tension_main),
        "tension_cross": int(obj.tension_cross),
        "promised_done_time": promised,
        "customer_name": c.name,
        "customer_phone": c.phone,
        "note": getattr(obj, "note", None),
    }


def staff_toggle_status_by_token(db: Session, token: str) -> Optional[Dict[str, Any]]:
    tok = (token or "").strip()
    obj = (
        db.query(models.OrderItem)
        .options(joinedload(models.OrderItem.order).joinedload(models.Order.customer))
        .filter(models.OrderItem.token == tok)
        .first()
    )
    if not obj or not obj.order or not obj.order.customer:
        return None

    old_status = _status_str(obj.status)
    obj.status = _cycle_status(obj.status)
    new_status = _status_str(obj.status)

    if new_status == "DONE" and obj.completed_at is None:
        obj.completed_at = datetime.utcnow()

    if new_status != "DONE" and old_status == "DONE" and new_status != "PICKED_UP":
        obj.completed_at = None

    db.commit()
    db.refresh(obj)

    c = obj.order.customer
    promised = obj.promised_done_time.strftime("%Y-%m-%d %H:%M") if obj.promised_done_time else None

    return {
        "token": obj.token,
        "order_no": getattr(obj, "order_no", None),
        "status": _status_str(obj.status),
        "string_type": obj.string_type,
        "tension_main": int(obj.tension_main),
        "tension_cross": int(obj.tension_cross),
        "promised_done_time": promised,
        "customer_name": c.name,
        "customer_phone": c.phone,
        "note": getattr(obj, "note", None),
    }
