from __future__ import annotations

import os
import io
from pathlib import Path
from datetime import datetime, date

from fastapi import Body, FastAPI, Depends, HTTPException, Request, Header
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func, cast
from sqlalchemy.types import Date as SqlDate
import qrcode

from .db import engine, Base, SessionLocal
from . import crud, schemas
from .models import OrderItem, ItemStatus

SHOP_NAME = "昇活運動用品館"
SHOP_PHONE = "0424181997"
LOGO_URL = "/static/logo.png"

MAP_URL = "https://www.google.com/maps/dir/?api=1&destination=" + SHOP_NAME
LINE_URL = "https://line.me/R/ti/p/@sheng-huo"

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
        raise HTTPException(status_code=403, detail="Forbidden")


def require_admin_key(x_admin_key: str = Header(default="")):
    if (x_admin_key or "").strip() != (ADMIN_KEY or "").strip():
        raise HTTPException(status_code=403, detail="Forbidden")


@app.get("/manifest.webmanifest")
def manifest():
    p = STATIC_DIR / "manifest.webmanifest"
    if not p.exists():
        raise HTTPException(status_code=404)
    return FileResponse(p, media_type="application/manifest+json")


@app.get("/sw.js")
def sw():
    p = STATIC_DIR / "sw.js"
    if not p.exists():
        raise HTTPException(status_code=404)
    return FileResponse(p, media_type="application/javascript")


@app.post("/customers", response_model=schemas.CustomerOut)
def create_customer(customer: schemas.CustomerCreate, db: Session = Depends(get_db)):
    return crud.create_customer(db, customer)


@app.post("/orders", response_model=schemas.ItemOut)
def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    return crud.create_order(db, order)


@app.patch("/items/{item_id}/status", response_model=schemas.ItemOut)
def change_status(item_id: int, status: str, db: Session = Depends(get_db)):
    item = crud.update_item_status(db, item_id, status)
    if not item:
        raise HTTPException(status_code=404)
    return item


@app.get("/items/{item_id}", response_model=schemas.ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    if not hasattr(crud, "get_item_by_id"):
        raise HTTPException(status_code=501, detail="crud.get_item_by_id not implemented")
    item = crud.get_item_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404)
    return item


@app.get("/public/{token}")
def public_info(token: str, db: Session = Depends(get_db)):
    data = crud.get_item_by_token(db, token)
    if not data:
        raise HTTPException(status_code=404)
    return JSONResponse(data)


@app.get("/api/track/{token}", response_model=schemas.TrackItemOut)
def api_track_by_token(token: str, db: Session = Depends(get_db)):
    obj = crud.get_item_by_token(db, token)
    if not obj:
        raise HTTPException(status_code=404, detail="找不到資料")
    return obj


@app.post("/api/staff/scan/{token}", response_model=schemas.TrackItemOut)
def api_staff_scan_toggle(token: str, db: Session = Depends(get_db)):
    obj = crud.staff_toggle_status_by_token(db, token)
    if not obj:
        raise HTTPException(status_code=404, detail="找不到資料")
    return obj


@app.get("/t/{token}")
def short_track_redirect(token: str):
    return RedirectResponse(url=f"/track/{token}", status_code=307)


@app.get("/track/{token}", response_class=HTMLResponse)
def track_page(token: str):
    html = f"""
<!doctype html>
<html lang="zh-Hant" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{SHOP_NAME}｜穿線資訊</title>
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#0b1220">
<style>
:root {{
  --bg0:#050b18; --bg1:#0b1220;
  --card: rgba(255,255,255,.08);
  --card2: rgba(0,0,0,.22);
  --text: rgba(255,255,255,.92);
  --muted: rgba(255,255,255,.68);
  --line: rgba(255,255,255,.14);
  --btn: rgba(255,255,255,.08);
  --btn2: rgba(255,255,255,.12);
}}
html[data-theme="light"] {{
  --bg0:#f3f6ff; --bg1:#ffffff;
  --card: rgba(0,0,0,.05);
  --card2: rgba(255,255,255,.65);
  --text: rgba(15,23,42,.92);
  --muted: rgba(15,23,42,.62);
  --line: rgba(15,23,42,.12);
  --btn: rgba(0,0,0,.05);
  --btn2: rgba(0,0,0,.08);
}}
* {{ box-sizing: border-box; }}
body {{
  margin:0; min-height:100vh;
  font-family:"Segoe UI","Microsoft JhengHei",system-ui,-apple-system,sans-serif;
  color: var(--text);
  display:flex; justify-content:center;
  padding: 18px 14px 28px;
  background: radial-gradient(1200px 600px at 20% 0%, rgba(96,165,250,.18), transparent 60%),
              radial-gradient(900px 600px at 80% 20%, rgba(52,211,153,.12), transparent 60%),
              linear-gradient(180deg, var(--bg0), var(--bg1));
  overflow-x:hidden;
}}
.container {{ width:min(560px, 100%); position:relative; }}
.card {{
  position: relative; z-index:1;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 22px;
  box-shadow: 0 30px 90px rgba(0,0,0,.35);
  overflow:hidden;
  backdrop-filter: blur(12px);
}}
.header {{
  padding: 18px 18px 12px;
  display:flex; gap:14px;
  align-items:center;
  justify-content: space-between;
}}
.brand {{ display:flex; gap:14px; align-items:center; min-width:0; }}
.logo {{
  width:58px; height:58px;
  border-radius:16px; overflow:hidden;
  background: var(--btn);
  border: 1px solid var(--line);
}}
.logo img {{ width:100%; height:100%; object-fit:contain; padding:6px; display:block; }}
.shopname {{ font-weight:900; font-size:19px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.phone {{ margin-top:6px; font-size:14px; color:var(--muted); }}
.phone a {{ color:var(--muted); text-decoration:none; }}
.divider {{ height:1px; background: var(--line); }}
.body {{ padding: 16px 18px 18px; }}
.grid {{ display:grid; grid-template-columns:1fr; gap:12px; }}
.row {{
  background: var(--card2);
  outline: 1px solid rgba(255,255,255,.06);
  border-radius:16px;
  padding:14px;
}}
.label {{ font-size:12px; color:var(--muted); letter-spacing:.8px; }}
.value {{ margin-top:6px; font-size:22px; font-weight:900; }}
.small {{ font-size:18px; font-weight:850; }}
.actions {{ margin-top:14px; display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
.btn {{
  display:flex; align-items:center; justify-content:center; gap:8px;
  padding: 12px;
  border-radius:14px;
  border:1px solid var(--line);
  background: var(--btn);
  color: var(--text);
  font-weight:950;
  text-decoration:none;
  cursor:pointer;
}}
.btn:hover {{ background: var(--btn2); }}
.btn-ghost {{ grid-column: 1 / -1; }}
.footer {{ margin-top:12px; color:var(--muted); font-size:12px; text-align:center; }}
@media (min-width:520px) {{
  .grid {{ grid-template-columns: 1fr 1fr; }}
  .row.full {{ grid-column: 1 / -1; }}
}}
</style>
</head>
<body>
  <div class="container">
    <div class="card">
      <div class="header">
        <div class="brand">
          <div class="logo"><img src="{LOGO_URL}" alt="logo"></div>
          <div>
            <div class="shopname">{SHOP_NAME}</div>
            <div class="phone">☎ <a href="tel:{SHOP_PHONE}">{SHOP_PHONE}</a></div>
          </div>
        </div>
        <button class="btn" id="themeBtn" type="button">🌙</button>
      </div>

      <div class="divider"></div>

      <div class="body">
        <div class="grid">
          <div class="row full">
            <div class="label">姓名</div>
            <div id="name" class="value">載入中…</div>
          </div>

          <div class="row">
            <div class="label">狀態</div>
            <div id="status" class="value small">-</div>
          </div>

          <div class="row">
            <div class="label">線種 / 磅數</div>
            <div class="value small"><span id="string">-</span>｜<span id="m">-</span>/<span id="c">-</span></div>
          </div>

          <div class="row full">
            <div class="label">預約完成</div>
            <div id="time" class="value small">-</div>
          </div>
        </div>

        <div class="actions">
          <a class="btn" href="{MAP_URL}" target="_blank" rel="noreferrer">📍 Google 導航</a>
          <a class="btn" href="{LINE_URL}" target="_blank" rel="noreferrer">💬 LINE 客服</a>
          <button class="btn btn-ghost" type="button" onclick="load()">🔄 手動更新</button>
        </div>

        <div class="footer">每 15 秒自動更新；若未更新請按「手動更新」</div>
      </div>
    </div>
  </div>

<script>
const token = "{token}";

function setTheme(theme) {{
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("theme", theme);
  document.getElementById("themeBtn").textContent = (theme === "light") ? "☀️" : "🌙";
}}
(function initTheme() {{
  const saved = localStorage.getItem("theme");
  setTheme(saved === "light" ? "light" : "dark");
}})();

document.getElementById("themeBtn").addEventListener("click", () => {{
  const cur = document.documentElement.getAttribute("data-theme") || "dark";
  setTheme(cur === "dark" ? "light" : "dark");
}});

function mapStatus(s) {{
  const x = (s || "").toUpperCase();
  if (x === "RECEIVED") return "已收拍";
  if (x === "WORKING") return "穿線中";
  if (x === "DONE") return "已完成";
  if (x === "PICKED_UP") return "已取拍";
  return s || "-";
}}

async function load() {{
  try {{
    const r = await fetch("/api/track/" + token, {{ cache: "no-store" }});
    if(!r.ok) return;
    const d = await r.json();
    document.getElementById("name").innerText = d.customer_name ?? "";
    document.getElementById("status").innerText = mapStatus(d.status);
    document.getElementById("string").innerText = d.string_type ?? "";
    document.getElementById("m").innerText = d.tension_main ?? "";
    document.getElementById("c").innerText = d.tension_cross ?? "";
    document.getElementById("time").innerText = d.promised_done_time ?? "";
  }} catch(e) {{}}
}}
load();
setInterval(load, 15000);

if ("serviceWorker" in navigator) {{
  navigator.serviceWorker.register("/sw.js").catch(() => {{}});
}}
</script>
</body>
</html>
"""
    return HTMLResponse(html)


@app.get("/qrcode/{token}")
def qrcode_img(token: str, request: Request, db: Session = Depends(get_db)):
    data = crud.get_item_by_token(db, token)
    if not data:
        raise HTTPException(status_code=404, detail="Not Found")

    base = str(request.base_url).rstrip("/")
    url = f"{base}/t/{token.strip()}"

    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


@app.post("/api/staff/toggle/{token}")
def api_staff_toggle(token: str, k: str, db: Session = Depends(get_db)):
    require_staff_key(k)
    item = crud.staff_toggle_status_by_token(db, token)
    if not item:
        raise HTTPException(status_code=404)
    return item


@app.get("/staff_toggle/{token}", response_class=HTMLResponse)
def staff_toggle_page(token: str, k: str = "", request: Request = None):
    require_staff_key(k)
    html = f"""
<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{SHOP_NAME}｜店員掃描</title>
<style>
  body {{
    margin:0; min-height:100vh;
    display:flex; align-items:center; justify-content:center;
    font-family:"Segoe UI","Microsoft JhengHei",system-ui,-apple-system,sans-serif;
    background:#0b1220; color:#fff;
  }}
  .card {{
    width:min(520px, 92vw);
    background: rgba(255,255,255,.08);
    border:1px solid rgba(255,255,255,.14);
    border-radius:22px;
    padding:18px;
    box-shadow: 0 30px 90px rgba(0,0,0,.35);
  }}
  .title {{ font-weight:900; font-size:18px; opacity:.9; }}
  .big {{ margin-top:14px; font-size:40px; font-weight:950; letter-spacing:.5px; }}
  .muted {{ margin-top:10px; opacity:.7; font-size:13px; line-height:1.6; }}
  .btn {{
    margin-top:14px; width:100%;
    padding:14px 12px; border-radius:16px;
    border:1px solid rgba(255,255,255,.14);
    background: rgba(255,255,255,.10);
    color:#fff; font-weight:950;
    cursor:pointer; font-size:16px;
  }}
</style>
</head>
<body>
  <div class="card">
    <div class="title">{SHOP_NAME}｜店員掃描（自動切狀態）</div>
    <div id="result" class="big">處理中…</div>
    <div id="hint" class="muted">Token：{token}</div>
    <button class="btn" onclick="toggle()">再切一次（手動）</button>
  </div>

<script>
const token = "{token}";
const key = "{k}";

function show(text, sub="") {{
  document.getElementById("result").innerText = text;
  document.getElementById("hint").innerText = sub || ("Token：" + token);
}}

function mapStatus(s) {{
  const x = (s || "").toUpperCase();
  if (x === "RECEIVED") return "已收拍";
  if (x === "WORKING") return "穿線中";
  if (x === "DONE") return "已完成";
  if (x === "PICKED_UP") return "已取拍";
  return s || "-";
}}

async function toggle(){{
  try {{
    const r = await fetch(`/api/staff/toggle/${{token}}?k=${{encodeURIComponent(key)}}`, {{
      method: "POST",
      cache: "no-store"
    }});
    if(!r.ok) {{
      if(r.status === 403) return show("🚫 無權限", "key 不對（請用店員 QR）");
      if(r.status === 404) return show("找不到", "token 不存在");
      return show("錯誤", "請回到上一頁再掃一次");
    }}
    const d = await r.json();
    show("✅ " + mapStatus(d.status), `訂單：${{d.order_no || "-"}}｜${{d.customer_name || ""}}`);
  }} catch(e) {{
    show("網路錯誤", "請確認同 Wi-Fi 並重掃");
  }}
}}
toggle();
</script>
</body>
</html>
"""
    return HTMLResponse(html)


@app.get("/qrcode_staff/{token}")
def qrcode_staff_img(token: str, request: Request, db: Session = Depends(get_db)):
    data = crud.get_item_by_token(db, token)
    if not data:
        raise HTTPException(status_code=404, detail="Not Found")

    base = str(request.base_url).rstrip("/")
    url = f"{base}/staff_toggle/{token.strip()}?k={STAFF_KEY}"

    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


@app.post("/api/admin/create_one", response_model=schemas.AdminCreateOneOut)
def api_admin_create_one(
    payload: schemas.AdminCreateOneIn,
    db: Session = Depends(get_db),
    _=Depends(require_admin_key),
):
    return crud.admin_create_one(db, payload)


@app.get("/api/admin/summary")
def api_admin_summary(
    date: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin_key),
):
    day = datetime.strptime(date, "%Y-%m-%d").date()
    return JSONResponse(crud.admin_summary_by_date(db, day))


@app.get("/api/admin/items")
def api_admin_items(
    date: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin_key),
):
    day = datetime.strptime(date, "%Y-%m-%d").date()
    data = crud.admin_list_items_by_date(db, day)
    return JSONResponse(data)


@app.get("/api/admin/search")
def api_admin_search(
    q: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin_key),
):
    return JSONResponse(crud.admin_search(db, q))


@app.patch("/api/admin/items/{item_id}/status")
def api_admin_set_status(
    item_id: int,
    status: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin_key),
):
    item = crud.update_item_status(db, item_id, status)
    if not item:
        raise HTTPException(status_code=404)
    return {"ok": True}


@app.patch("/api/admin/items/{item_id}/promised_done_time")
def api_admin_set_time(
    item_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _=Depends(require_admin_key),
):
    s = (payload.get("promised_done_time") or "").strip()
    if not s:
        raise HTTPException(status_code=400, detail="promised_done_time required")
    try:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M")
    except Exception:
        raise HTTPException(status_code=400, detail="format must be YYYY-MM-DD HH:MM")

    item = crud.update_promised_done_time(db, item_id, dt)
    if not item:
        raise HTTPException(status_code=404)
    return {"ok": True}


@app.get("/api/admin/month_unfinished")
def api_admin_month_unfinished(
    ym: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin_key),
):
    try:
        y, m = map(int, ym.split("-"))
        start = date(y, m, 1)
        end = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ym format. Use YYYY-MM")

    rows = (
        db.query(
            cast(OrderItem.promised_done_time, SqlDate).label("d"),
            func.count(OrderItem.id).label("cnt"),
        )
        .filter(OrderItem.promised_done_time >= start)
        .filter(OrderItem.promised_done_time < end)
        .filter(OrderItem.status.notin_([ItemStatus.DONE, ItemStatus.PICKED_UP]))
        .group_by(cast(OrderItem.promised_done_time, SqlDate))
        .all()
    )

    days: dict[str, int] = {}
    for r in rows:
        if not r.d:
            continue
        key = str(r.d)
        days[key] = int(r.cnt)

    return JSONResponse(content={"ym": str(ym), "days": days})


@app.get("/health")
def health():
    return {"ok": True}
