# trigger commit

from __future__ import annotations

import os
import io
from pathlib import Path
from datetime import datetime, date

from fastapi import Body, FastAPI, Depends, HTTPException, Request, Header
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import qrcode

from .db import engine, Base, SessionLocal
from . import crud, schemas


# =====================
# 店家設定
# =====================

SHOP_NAME = "昇活運動用品館"
SHOP_PHONE = "0424181997"
LOGO_URL = "/static/logo.png"

STAFF_KEY = os.getenv("STAFF_KEY", "CL3KX7")
ADMIN_KEY = os.getenv("ADMIN_KEY", "CHANGE_ME")

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR), check_dir=False), name="static")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_staff_key(k: str):
    if (k or "").strip() != (STAFF_KEY or "").strip():
        raise HTTPException(status_code=403)


def require_admin_key(x_admin_key: str = Header(default="")):
    if (x_admin_key or "").strip() != (ADMIN_KEY or "").strip():
        raise HTTPException(status_code=403)


# =====================================================
# 基本 API
# =====================================================

@app.post("/customers", response_model=schemas.CustomerOut)
def create_customer(customer: schemas.CustomerCreate, db: Session = Depends(get_db)):
    return crud.create_customer(db, customer)


@app.post("/orders", response_model=schemas.ItemOut)
def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    return crud.create_order(db, order)


# =====================================================
# 客人頁
# =====================================================

@app.get("/public/{token}")
def public_info(token: str, db: Session = Depends(get_db)):
    data = crud.get_item_by_token(db, token)
    if not data:
        raise HTTPException(status_code=404)

    return {
        "name": data.get("name", ""),
        "string_type": data.get("string_type", ""),
        "tension_main": data.get("tension_main", ""),
        "tension_cross": data.get("tension_cross", ""),
        "done_time": data.get("done_time", ""),
    }


@app.get("/track/{token}", response_class=HTMLResponse)
def track_page(token: str):
    return HTMLResponse(f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{SHOP_NAME}</title>
</head>
<body style="font-family:sans-serif;padding:40px;">
<h2>穿線資訊</h2>
<div id="info">載入中...</div>

<script>
async function load(){{
  const r = await fetch("/public/{token}");
  if(!r.ok) return;
  const d = await r.json();
  document.getElementById("info").innerHTML =
    "姓名：" + d.name + "<br>" +
    "線種：" + d.string_type + "<br>" +
    "磅數：" + d.tension_main + " / " + d.tension_cross + "<br>" +
    "完成時間：" + d.done_time;
}}
load();
</script>
</body>
</html>
""")


@app.get("/qrcode/{token}")
def qrcode_img(token: str, request: Request):
    base = str(request.base_url).rstrip("/")
    url = f"{base}/track/{token}"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


# =====================================================
# 店員功能
# =====================================================

@app.post("/api/staff/toggle/{token}")
def staff_toggle(token: str, k: str, db: Session = Depends(get_db)):
    require_staff_key(k)
    item = crud.staff_toggle_status_by_token(db, token)
    if not item:
        raise HTTPException(status_code=404)
    return {"status": item.status.value}


@app.get("/staff_toggle/{token}", response_class=HTMLResponse)
def staff_toggle_page(token: str, k: str = ""):
    require_staff_key(k)
    return HTMLResponse(f"""
<html>
<body style="font-family:sans-serif;text-align:center;padding:60px;">
<h2>店員掃描</h2>
<div id="result">處理中...</div>
<script>
fetch("/api/staff/toggle/{token}?k={k}", {{method:"POST"}})
.then(r=>r.json())
.then(d=>{{
 document.getElementById("result").innerHTML="狀態：" + d.status;
}});
</script>
</body>
</html>
""")


@app.get("/qrcode_staff/{token}")
def qrcode_staff(token: str, request: Request):
    base = str(request.base_url).rstrip("/")
    url = f"{base}/staff_toggle/{token}?k={STAFF_KEY}"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


# =====================================================
# ✅ Admin APIs
# =====================================================

@app.post("/api/admin/create_one", response_model=schemas.AdminCreateOneOut)
def api_admin_create_one(
    payload: schemas.AdminCreateOneIn,
    db: Session = Depends(get_db),
    _=Depends(require_admin_key),
):
    return crud.admin_create_one(db, payload)


@app.get("/health")
def health():
    return {"ok": True}
