from __future__ import annotations

import io
from pathlib import Path
from datetime import datetime, date

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import qrcode

from .db import engine, Base, SessionLocal
from . import crud, schemas


# ===== 店家設定 =====
SHOP_NAME = "昇活運動用品館"
SHOP_PHONE = "0424181997"
LOGO_URL = "/static/logo.png"

MAP_URL = "https://www.google.com/maps/dir/?api=1&destination=" + SHOP_NAME
LINE_URL = "https://line.me/R/ti/p/@sheng-huo"

# ✅ 店員 key（掃店員 QR 才能切狀態）
STAFF_KEY = "CL3KX7"


app = FastAPI()

# =====================
# ✅ Static 設定（Render / 本機都穩）
# 目前 main.py 位置：/app/backend/app/main.py
# static 位置：         /app/backend/app/static
# =====================
BASE_DIR = Path(__file__).resolve().parent          # .../backend/app
STATIC_DIR = BASE_DIR / "static"                   # .../backend/app/static
STATIC_DIR.mkdir(parents=True, exist_ok=True)      # 沒有就建立，避免 RuntimeError

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =====================
# PWA files (manifest + service worker)
# =====================
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


# =====================
# 後台 API（原本）
# =====================
@app.post("/customers")
def create_customer(customer: schemas.CustomerCreate, db: Session = Depends(get_db)):
    return crud.create_customer(db, customer)


@app.post("/orders")
def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    return crud.create_order(db, order)


@app.patch("/items/{item_id}/status")
def change_status(item_id: int, status: str, db: Session = Depends(get_db)):
    item = crud.update_item_status(db, item_id, status)
    if not item:
        raise HTTPException(status_code=404)
    return item


# =====================
# ✅ 客人公開資料 API（只回 4 欄位）
# =====================
@app.get("/public/{token}")
def public_info(token: str, db: Session = Depends(get_db)):
    data = crud.get_item_by_token(db, token)
    if not data:
        raise HTTPException(status_code=404)

    return JSONResponse(
        {
            "name": data.get("name", ""),
            "string_type": data.get("string_type", ""),
            "tension_main": data.get("tension_main", ""),
            "tension_cross": data.get("tension_cross", ""),
            "done_time": data.get("done_time", ""),
        }
    )


# =====================
# ✅ 客人頁（美化版，只顯示 4 欄位）
# =====================
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
  --bg0:#050b18;
  --bg1:#0b1220;
  --card: rgba(255,255,255,.08);
  --card2: rgba(0,0,0,.22);
  --text: rgba(255,255,255,.92);
  --muted: rgba(255,255,255,.68);
  --line: rgba(255,255,255,.14);
  --btn: rgba(255,255,255,.08);
  --btn2: rgba(255,255,255,.12);
}}
html[data-theme="light"] {{
  --bg0:#f3f6ff;
  --bg1:#ffffff;
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
  margin:0;
  min-height:100vh;
  font-family: "Segoe UI","Microsoft JhengHei",system-ui,-apple-system,sans-serif;
  color: var(--text);
  display:flex;
  justify-content:center;
  padding: 18px 14px 28px;
  background: radial-gradient(1200px 600px at 20% 0%, rgba(96,165,250,.18), transparent 60%),
              radial-gradient(900px 600px at 80% 20%, rgba(52,211,153,.12), transparent 60%),
              linear-gradient(180deg, var(--bg0), var(--bg1));
  overflow-x:hidden;
}}
.container {{
  width: min(560px, 100%);
  position: relative;
}}
.blob {{
  position:absolute;
  width: 340px;
  height: 340px;
  border-radius: 999px;
  filter: blur(50px);
  opacity: .55;
  z-index: 0;
  animation: float 10s ease-in-out infinite;
  pointer-events:none;
}}
.blob.b1 {{
  left: -120px;
  top: -120px;
  background: radial-gradient(circle at 30% 30%, rgba(96,165,250,.85), transparent 60%);
}}
.blob.b2 {{
  right: -140px;
  top: 80px;
  background: radial-gradient(circle at 30% 30%, rgba(52,211,153,.70), transparent 60%);
  animation-delay: -3s;
}}
.blob.b3 {{
  left: 40px;
  bottom: -180px;
  background: radial-gradient(circle at 30% 30%, rgba(167,139,250,.55), transparent 60%);
  animation-delay: -6s;
}}
@keyframes float {{
  0%   {{ transform: translate3d(0,0,0) scale(1); }}
  50%  {{ transform: translate3d(0,18px,0) scale(1.05); }}
  100% {{ transform: translate3d(0,0,0) scale(1); }}
}}
.card {{
  position: relative;
  z-index: 1;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 22px;
  box-shadow: 0 30px 90px rgba(0,0,0,.35);
  overflow:hidden;
  backdrop-filter: blur(12px);
}}
.header {{
  padding: 18px 18px 12px;
  display:flex;
  gap:14px;
  align-items:center;
  justify-content: space-between;
}}
.brand {{
  display:flex;
  gap:14px;
  align-items:center;
  min-width:0;
}}
.logo {{
  width: 58px;
  height: 58px;
  border-radius: 16px;
  overflow:hidden;
  background: var(--btn);
  border: 1px solid var(--line);
  flex: 0 0 auto;
}}
.logo img {{
  width:100%;
  height:100%;
  object-fit:contain;
  display:block;
  padding:6px;
}}
.shopname {{
  font-weight: 900;
  letter-spacing: .4px;
  font-size: 19px;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.phone {{
  margin-top: 6px;
  font-size: 14px;
  color: var(--muted);
}}
.phone a {{
  color: var(--muted);
  text-decoration:none;
}}
.phone a:hover {{ text-decoration: underline; }}

.top-actions {{
  display:flex;
  gap:10px;
  align-items:center;
}}
.iconbtn {{
  border: 1px solid var(--line);
  background: var(--btn);
  color: var(--text);
  border-radius: 14px;
  padding: 10px 12px;
  font-weight: 900;
  cursor:pointer;
}}
.iconbtn:hover {{ background: var(--btn2); }}

.divider {{
  height:1px;
  background: var(--line);
}}
.body {{
  padding: 16px 18px 18px;
}}
.grid {{
  display:grid;
  grid-template-columns: 1fr;
  gap: 12px;
}}
.row {{
  background: var(--card2);
  outline: 1px solid rgba(255,255,255,.06);
  border-radius: 16px;
  padding: 14px 14px;
}}
.label {{
  font-size: 12px;
  color: var(--muted);
  letter-spacing: .8px;
}}
.value {{
  margin-top: 6px;
  font-size: 22px;
  font-weight: 900;
  letter-spacing: .2px;
}}
.small {{
  font-size: 18px;
  font-weight: 850;
}}
.actions {{
  margin-top: 14px;
  display:grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}}
.btn {{
  display:flex;
  align-items:center;
  justify-content:center;
  gap: 8px;
  width:100%;
  padding: 12px 12px;
  border-radius: 14px;
  border: 1px solid var(--line);
  cursor:pointer;
  font-weight: 950;
  user-select:none;
  text-decoration:none;
  background: var(--btn);
  color: var(--text);
}}
.btn:hover {{ background: var(--btn2); }}
.btn-ghost {{
  grid-column: 1 / -1;
}}
.footer {{
  margin-top: 12px;
  color: var(--muted);
  font-size: 12px;
  text-align:center;
}}
@media (min-width: 520px) {{
  .grid {{
    grid-template-columns: 1fr 1fr;
  }}
  .row.full {{
    grid-column: 1 / -1;
  }}
  .value {{ font-size: 24px; }}
}}
</style>
</head>
<body>
  <div class="container">
    <div class="blob b1"></div>
    <div class="blob b2"></div>
    <div class="blob b3"></div>

    <div class="card">
      <div class="header">
        <div class="brand">
          <div class="logo"><img src="{LOGO_URL}" alt="logo"></div>
          <div>
            <div class="shopname">{SHOP_NAME}</div>
            <div class="phone">☎ <a href="tel:{SHOP_PHONE}">{SHOP_PHONE}</a></div>
          </div>
        </div>

        <div class="top-actions">
          <button class="iconbtn" id="themeBtn" type="button">🌙</button>
        </div>
      </div>

      <div class="divider"></div>

      <div class="body">
        <div class="grid">
          <div class="row full">
            <div class="label">姓名</div>
            <div id="name" class="value">載入中…</div>
          </div>

          <div class="row">
            <div class="label">線種</div>
            <div id="string" class="value small">-</div>
          </div>

          <div class="row">
            <div class="label">磅數</div>
            <div class="value small"><span id="m">-</span> / <span id="c">-</span></div>
          </div>

          <div class="row full">
            <div class="label">穿線時間</div>
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
  if (saved === "light" || saved === "dark") {{
    setTheme(saved);
  }} else {{
    setTheme("dark");
  }}
}})();

document.getElementById("themeBtn").addEventListener("click", () => {{
  const cur = document.documentElement.getAttribute("data-theme") || "dark";
  setTheme(cur === "dark" ? "light" : "dark");
}});

async function load() {{
  try {{
    const r = await fetch("/public/" + token, {{ cache: "no-store" }});
    if(!r.ok) return;
    const d = await r.json();
    document.getElementById("name").innerText = d.name ?? "";
    document.getElementById("string").innerText = d.string_type ?? "";
    document.getElementById("m").innerText = d.tension_main ?? "";
    document.getElementById("c").innerText = d.tension_cross ?? "";
    document.getElementById("time").innerText = d.done_time ?? "";
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


# =====================
# QRCode 產生（客人用：導到 /track/{token}）
# =====================
@app.get("/qrcode/{token}")
def qrcode_img(token: str, request: Request, db: Session = Depends(get_db)):
    data = crud.get_item_by_token(db, token)
    if not data:
        raise HTTPException(status_code=404, detail="Not Found")

    base = str(request.base_url).rstrip("/")
    url = f"{base}/track/{token.strip()}"

    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


# =====================
# ✅ 店員：切狀態 API（需 key）
# =====================
@app.post("/api/staff/toggle/{token}")
def api_staff_toggle(token: str, k: str, db: Session = Depends(get_db)):
    if (k or "").strip() != STAFF_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

    item = crud.staff_toggle_status_by_token(db, token)
    if not item:
        raise HTTPException(status_code=404)

    st = item.status.value if hasattr(item.status, "value") else str(item.status)
    st = st.replace("ItemStatus.", "")
    return {"ok": True, "token": item.token, "status": st}


# =====================
# ✅ 店員掃描頁：掃到就自動切一次
# =====================
@app.get("/staff/{token}", response_class=HTMLResponse)
def staff_page(token: str, k: str = "", request: Request = None):
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
  .big {{
    margin-top:14px;
    font-size:40px; font-weight:950;
    letter-spacing:.5px;
  }}
  .muted {{ margin-top:10px; opacity:.7; font-size:13px; line-height:1.6; }}
  .btn {{
    margin-top:14px;
    width:100%;
    padding:14px 12px;
    border-radius:16px;
    border:1px solid rgba(255,255,255,.14);
    background: rgba(255,255,255,.10);
    color:#fff;
    font-weight:950;
    cursor:pointer;
    font-size:16px;
  }}
  .btn:active {{ transform: scale(.99); }}
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
    show("✅ " + (d.status || "OK"), "已更新狀態｜Token：" + token);
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


# =====================
# ✅ 店員 QRCode（導到 /staff/{token}?k=...） -> PNG
# =====================
@app.get("/qrcode_staff/{token}")
def qrcode_staff_img(token: str, request: Request, db: Session = Depends(get_db)):
    data = crud.get_item_by_token(db, token)
    if not data:
        raise HTTPException(status_code=404, detail="Not Found")

    base = str(request.base_url).rstrip("/")
    url = f"{base}/staff/{token.strip()}?k={STAFF_KEY}"

    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


# =====================
# ✅ Admin APIs
# =====================
@app.get("/api/admin/summary")
def api_admin_summary(date: str, db: Session = Depends(get_db)):
    day = datetime.strptime(date, "%Y-%m-%d").date()
    return JSONResponse(crud.admin_summary_by_date(db, day))


@app.get("/api/admin/items")
def api_admin_items(date: str, db: Session = Depends(get_db)):
    day = datetime.strptime(date, "%Y-%m-%d").date()
    return JSONResponse(crud.admin_list_items_by_date(db, day))


@app.get("/api/admin/search")
def api_admin_search(q: str, db: Session = Depends(get_db)):
    return JSONResponse(crud.admin_search(db, q))


@app.patch("/api/admin/items/{item_id}/status")
def api_admin_set_status(item_id: int, status: str, db: Session = Depends(get_db)):
    item = crud.update_item_status(db, item_id, status)
    if not item:
        raise HTTPException(status_code=404)
    return {"ok": True}


@app.patch("/api/admin/items/{item_id}/promised_done_time")
def api_admin_set_time(item_id: int, payload: dict, db: Session = Depends(get_db)):
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


# =====================
# ✅ 店家後台頁（/admin）
# =====================
@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    today = date.today().strftime("%Y-%m-%d")
    html = f"""
<!doctype html>
<html lang="zh-Hant" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{SHOP_NAME}｜店家後台</title>
<meta name="theme-color" content="#0b1220">
<style>
:root {{
  --bg0:#050b18;
  --bg1:#0b1220;
  --card: rgba(255,255,255,.08);
  --card2: rgba(0,0,0,.20);
  --text: rgba(255,255,255,.92);
  --muted: rgba(255,255,255,.65);
  --line: rgba(255,255,255,.14);
  --btn: rgba(255,255,255,.08);
  --btn2: rgba(255,255,255,.12);
}}
*{{box-sizing:border-box}}
body {{
  margin:0;
  min-height:100vh;
  font-family:"Segoe UI","Microsoft JhengHei",system-ui,-apple-system,sans-serif;
  color:var(--text);
  display:flex;
  justify-content:center;
  padding:18px 14px 28px;
  background:
    radial-gradient(1200px 600px at 20% 0%, rgba(96,165,250,.18), transparent 60%),
    radial-gradient(900px 600px at 80% 20%, rgba(52,211,153,.12), transparent 60%),
    linear-gradient(180deg, var(--bg0), var(--bg1));
  overflow-x:hidden;
}}
.container{{width:min(1000px,100%); position:relative}}
.card{{position:relative;z-index:1;background:var(--card);border:1px solid var(--line);border-radius:22px;box-shadow:0 30px 90px rgba(0,0,0,.35);overflow:hidden;backdrop-filter: blur(12px)}}
.header{{padding:16px 16px 12px;display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}}
.brand{{display:flex;gap:12px;align-items:center;min-width:0}}
.logo{{width:54px;height:54px;border-radius:16px;overflow:hidden;background:var(--btn);border:1px solid var(--line);flex:0 0 auto}}
.logo img{{width:100%;height:100%;object-fit:contain;display:block;padding:6px}}
.shopname{{font-weight:950;font-size:18px;letter-spacing:.3px}}
.phone{{font-size:13px;color:var(--muted);margin-top:4px}}
.right{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
input,button{{border-radius:14px;border:1px solid var(--line);background:var(--btn);color:var(--text);padding:12px 14px;font-weight:900}}
input[type="date"]{{padding:10px 12px}}
input::placeholder{{color:rgba(255,255,255,.45)}}
button{{cursor:pointer}}
button:hover{{background:var(--btn2)}}
.divider{{height:1px;background:var(--line)}}

.section{{padding:14px 16px 16px}}
.grid{{display:grid;grid-template-columns:1fr;gap:12px}}
@media (min-width:820px){{.grid{{grid-template-columns:1.2fr .8fr}}}}

.box{{background:var(--card2);outline: 1px solid rgba(255,255,255,.06);border-radius:18px;padding:14px}}
.k{{font-size:12px;color:var(--muted);letter-spacing:.8px}}
.v{{margin-top:6px;font-size:24px;font-weight:950}}
.mini{{font-size:12px;color:var(--muted);line-height:1.8}}

.list{{display:flex;flex-direction:column;gap:10px}}
.item{{background:var(--card2);outline: 1px solid rgba(255,255,255,.06);border-radius:18px;padding:14px;display:flex;flex-direction:column;gap:10px}}
.itop{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-start}}
.time{{font-weight:950;font-size:20px}}
.token{{font-size:12px;color:var(--muted)}}
.name{{font-weight:950;font-size:16px}}
.sub{{font-size:13px;color:var(--muted)}}

.dot{{width:10px;height:10px;border-radius:999px;display:inline-block}}
.dot.r{{background:#9ca3af}}
.dot.w{{background:#f59e0b}}
.dot.d{{background:#22c55e}}
.dot.p{{background:#a78bfa}}
.badge{{border:1px solid var(--line);border-radius:999px;padding:6px 10px;font-weight:950;font-size:12px;background:rgba(255,255,255,.04)}}
.donebig{{font-weight:950;color:#22c55e}}

.actions{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
@media (min-width:520px){{.actions{{grid-template-columns:repeat(5, 1fr)}}}}
.abtn{{padding:14px 10px;border-radius:14px;border:1px solid var(--line);background:var(--btn);font-weight:950;cursor:pointer;text-align:center}}
.abtn:hover{{background:var(--btn2)}}
.abtn.small{{grid-column:1/-1}}
@media (min-width:520px){{.abtn.small{{grid-column:auto}}}}

.hint{{padding:10px 16px 14px;color:var(--muted);font-size:12px;text-align:center}}
</style>
</head>
<body>
  <div class="container">
    <div class="card">
      <div class="header">
        <div class="brand">
          <div class="logo"><img src="{LOGO_URL}" alt="logo"></div>
          <div>
            <div class="shopname">{SHOP_NAME}｜店家後台</div>
            <div class="phone">☎ {SHOP_PHONE}</div>
          </div>
        </div>

        <div class="right">
          <input id="day" type="date" value="{today}">
          <input id="q" placeholder="搜尋 token / 姓名 / 電話" style="min-width:220px;">
          <button onclick="loadAll()">更新</button>
        </div>
      </div>

      <div class="divider"></div>

      <div class="section">
        <div class="grid">
          <div class="box">
            <div class="k">當日總數</div>
            <div class="v" id="total">-</div>
            <div class="mini" id="statusStat">-</div>
          </div>

          <div class="box">
            <div class="k">幾點有幾支</div>
            <div class="mini" id="hourStat">-</div>
          </div>
        </div>

        <div style="height:12px"></div>

        <div class="box">
          <div class="k">清單（依完成時間排序）</div>
          <div class="list" id="list"></div>
        </div>

        <div class="hint">自動每 10 秒刷新；也可按「更新」</div>
      </div>
    </div>
  </div>

<script>
function statusDot(s){{
  s=(s||"").toUpperCase();
  if(s==="RECEIVED") return "r";
  if(s==="WORKING") return "w";
  if(s==="DONE") return "d";
  if(s==="PICKED_UP") return "p";
  return "r";
}}

function escapeHtml(str) {{
  return (str??"").toString()
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}}

async function loadSummary(day){{
  const r = await fetch(`/api/admin/summary?date=${{day}}`, {{cache:"no-store"}});
  const d = await r.json();
  total.innerText = d.total ?? 0;

  const bs=d.by_status||{{}};
  statusStat.innerText =
    `RECEIVED ${{bs.RECEIVED||0}}｜WORKING ${{bs.WORKING||0}}｜DONE ${{bs.DONE||0}}｜PICKED_UP ${{bs.PICKED_UP||0}}`;

  const bh=d.by_hour||{{}};
  let lines=[];
  for(let h=0; h<24; h++) {{
    const hh=String(h).padStart(2,"0");
    const cnt=bh[hh]||0;
    if(cnt>0) lines.push(`${{hh}}:00 → ${{cnt}} 支`);
  }}
  hourStat.innerHTML = lines.length ? lines.join("<br>") : "今天沒有資料";
}}

function renderItems(items){{
  const root = document.getElementById("list");
  root.innerHTML = "";
  if(!items || items.length===0){{
    root.innerHTML = '<div class="mini" style="padding:8px 2px;">沒有資料</div>';
    return;
  }}

  for(const it of items){{
    const time = (it.promised_done_time||"").slice(11,16);
    const token = it.token || "";
    const name = it.customer_name || "";
    const phone = it.customer_phone || "";
    const st = (it.status||"").toUpperCase();
    const dot = statusDot(st);

    const card = document.createElement("div");
    card.className = "item";
    card.innerHTML = `
      <div class="itop">
        <div>
          <div class="time">${{escapeHtml(time)}} <span class="badge"><span class="dot ${{dot}}"></span> ${{escapeHtml(st)}}</span>
            ${{st==="DONE" ? '<span class="badge donebig">🟢 可取拍</span>' : ''}}
          </div>
          <div class="token">TOKEN：${{escapeHtml(token)}}</div>
        </div>
        <div style="text-align:right">
          <div class="name">${{escapeHtml(name)}}</div>
          <div class="sub">${{escapeHtml(phone)}}</div>
        </div>
      </div>

      <div class="sub">線：<b>${{escapeHtml(it.string_type||"")}}</b>　磅：<b>${{it.tension_main}}</b> / <b>${{it.tension_cross}}</b>　完成：<b>${{escapeHtml(it.promised_done_time||"")}}</b></div>

      <div class="actions">
        <div class="abtn" onclick="setStatus(${{it.id}},'RECEIVED')">RECEIVED</div>
        <div class="abtn" onclick="setStatus(${{it.id}},'WORKING')">WORKING</div>
        <div class="abtn" onclick="setStatus(${{it.id}},'DONE')">DONE</div>
        <div class="abtn" onclick="setStatus(${{it.id}},'PICKED_UP')">PICKED_UP</div>
        <div class="abtn small" onclick="editTime(${{it.id}}, '${{escapeHtml(it.promised_done_time||"")}}')">改完成時間</div>
      </div>
    `;
    root.appendChild(card);
  }}
}}

async function loadItems(day){{
  const r = await fetch(`/api/admin/items?date=${{day}}`, {{cache:"no-store"}});
  const items = await r.json();
  renderItems(items);
}}

async function search(){{
  const kw = document.getElementById("q").value.trim();
  if(!kw){{
    loadAll();
    return;
  }}
  const r = await fetch(`/api/admin/search?q=${{encodeURIComponent(kw)}}`, {{cache:"no-store"}});
  const items = await r.json();
  renderItems(items);
}}

async function setStatus(id, st){{
  const r = await fetch(`/api/admin/items/${{id}}/status?status=${{st}}`, {{method:"PATCH"}});
  if(r.ok) {{
    const day=document.getElementById("day").value;
    await loadSummary(day);
    await search();
  }}
}}

async function editTime(id, cur){{
  const v = prompt("輸入新的完成時間（格式：YYYY-MM-DD HH:MM）", cur);
  if(!v) return;
  const r = await fetch(`/api/admin/items/${{id}}/promised_done_time`, {{
    method:"PATCH",
    headers:{{"Content-Type":"application/json"}},
    body: JSON.stringify({{ promised_done_time: v }})
  }});
  if(r.ok) {{
    const day=document.getElementById("day").value;
    await loadSummary(day);
    await search();
  }}
}}

async function loadAll(){{
  const day=document.getElementById("day").value;
  await loadSummary(day);
  await loadItems(day);
}}

document.getElementById("q").addEventListener("input", () => {{
  window.clearTimeout(window.__t);
  window.__t = window.setTimeout(search, 300);
}});

document.getElementById("day").addEventListener("change", () => {{
  document.getElementById("q").value = "";
  loadAll();
}});

loadAll();
setInterval(() => {{
  const kw=document.getElementById("q").value.trim();
  if(kw) search();
  else loadAll();
}}, 10000);
</script>
</body>
</html>
"""
    return HTMLResponse(html)


# =====================
# ✅（改名避免跟 /qrcode_staff/{token} 衝突）
# ✅ 店員掃碼：秒切狀態（掃 QR 直接進這頁）
# =====================
@app.get("/staff_toggle/{token}", response_class=HTMLResponse)
def staff_qr_toggle(token: str, db: Session = Depends(get_db)):
    info = crud.get_item_by_token(db, token)
    if not info:
        raise HTTPException(status_code=404, detail="Not Found")

    item = crud.staff_toggle_status_by_token(db, token)
    if not item:
        raise HTTPException(status_code=500, detail="toggle failed")

    new_status = item.status.value if hasattr(item.status, "value") else str(item.status)
    new_status = new_status.replace("ItemStatus.", "")

    badge = {
        "RECEIVED": ("#9ca3af", "已收件"),
        "WORKING": ("#f59e0b", "處理中"),
        "DONE": ("#22c55e", "已完成"),
        "PICKED_UP": ("#a78bfa", "已取拍"),
    }.get(new_status, ("#60a5fa", new_status))

    color, zh = badge

    html = f"""
<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{SHOP_NAME}｜店員掃碼</title>
<style>
  body {{
    margin:0; min-height:100vh; display:flex; justify-content:center; align-items:center;
    font-family:"Segoe UI","Microsoft JhengHei",system-ui,-apple-system,sans-serif;
    background: linear-gradient(180deg, #050b18, #0b1220);
    color: rgba(255,255,255,.92);
    padding: 18px;
  }}
  .card {{
    width: min(560px, 100%);
    background: rgba(255,255,255,.08);
    border: 1px solid rgba(255,255,255,.14);
    border-radius: 22px;
    box-shadow: 0 30px 90px rgba(0,0,0,.35);
    padding: 18px;
    backdrop-filter: blur(12px);
  }}
  .top {{
    display:flex; gap:12px; align-items:center; justify-content:space-between; flex-wrap:wrap;
  }}
  .brand {{
    display:flex; gap:12px; align-items:center;
  }}
  .logo {{
    width:54px; height:54px; border-radius:16px; overflow:hidden;
    background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.14);
  }}
  .logo img {{ width:100%; height:100%; object-fit:contain; padding:6px; display:block; }}
  .shopname {{ font-weight:950; font-size:18px; letter-spacing:.3px; }}
  .badge {{
    display:inline-flex; align-items:center; gap:8px;
    padding:10px 12px;
    border-radius: 999px;
    border: 1px solid rgba(255,255,255,.18);
    background: rgba(0,0,0,.25);
    font-weight:950;
  }}
  .dot {{
    width:10px; height:10px; border-radius:999px; background:{color};
    box-shadow: 0 0 18px {color};
  }}
  .grid {{
    margin-top:14px;
    display:grid; grid-template-columns: 1fr; gap: 10px;
  }}
  .row {{
    background: rgba(0,0,0,.22);
    border-radius: 16px;
    outline: 1px solid rgba(255,255,255,.06);
    padding: 14px;
  }}
  .k {{ font-size:12px; color: rgba(255,255,255,.65); letter-spacing:.8px; }}
  .v {{ margin-top:6px; font-size:20px; font-weight:950; }}
  .muted {{ color: rgba(255,255,255,.65); font-size:12px; margin-top:12px; text-align:center; line-height:1.7; }}
  .btn {{
    margin-top: 12px;
    width:100%;
    display:flex; justify-content:center; align-items:center;
    padding: 12px;
    border-radius: 14px;
    border: 1px solid rgba(255,255,255,.14);
    background: rgba(255,255,255,.08);
    color: rgba(255,255,255,.92);
    text-decoration:none;
    font-weight:950;
  }}
  .btn:hover {{ background: rgba(255,255,255,.12); }}
</style>
</head>
<body>
  <div class="card">
    <div class="top">
      <div class="brand">
        <div class="logo"><img src="{LOGO_URL}" alt="logo"></div>
        <div>
          <div class="shopname">{SHOP_NAME}｜店員掃碼</div>
          <div style="color:rgba(255,255,255,.65);font-size:12px;margin-top:4px;">掃一次就切狀態</div>
        </div>
      </div>
      <div class="badge"><span class="dot"></span> {zh}（{new_status}）</div>
    </div>

    <div class="grid">
      <div class="row">
        <div class="k">姓名</div>
        <div class="v">{info.get("customer_name_raw","")}</div>
      </div>
      <div class="row">
        <div class="k">線種</div>
        <div class="v">{info.get("string_type","")}</div>
      </div>
      <div class="row">
        <div class="k">磅數</div>
        <div class="v">{info.get("tension_main","")} / {info.get("tension_cross","")}</div>
      </div>
      <div class="row">
        <div class="k">穿線時間</div>
        <div class="v">{info.get("done_time","")}</div>
      </div>
    </div>

    <a class="btn" href="/admin" target="_blank" rel="noreferrer">打開店家後台</a>
    <div class="muted">✅ 已完成狀態切換<br>（若你連掃兩次會繼續往下一階）</div>
  </div>
</body>
</html>
"""
    return HTMLResponse(html)


@app.get("/health")
def health():
    return {"ok": True}
