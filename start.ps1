$ErrorActionPreference = "Stop"

# ===== 你的專案路徑（自動抓 START.bat 所在資料夾）=====
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND = Join-Path $ROOT "backend"
$VENV_ACT = Join-Path $BACKEND ".venv\Scripts\Activate.ps1"

Write-Host "== Racket Stringing 一鍵啟動 ==" -ForegroundColor Cyan
Write-Host "Project: $ROOT" -ForegroundColor DarkGray

# ===== 1) 啟動 Docker compose（DB）=====
Write-Host "`n[1/3] 啟動 Docker compose..." -ForegroundColor Yellow
Set-Location $ROOT

# 檢查 docker 指令是否可用
try {
  docker version | Out-Null
} catch {
  Write-Host "找不到 docker 指令 / Docker Desktop 可能沒開。" -ForegroundColor Red
  Write-Host "請先打開 Docker Desktop 再重試。" -ForegroundColor Red
  Pause
  exit 1
}

docker compose up -d
if ($LASTEXITCODE -ne 0) {
  Write-Host "docker compose up 失敗，請檢查 docker-compose.yml" -ForegroundColor Red
  Pause
  exit 1
}

Write-Host "Docker compose 已啟動。" -ForegroundColor Green

# ===== 2) 啟動 FastAPI（uvicorn）=====
Write-Host "`n[2/3] 啟動 FastAPI (uvicorn)..." -ForegroundColor Yellow

if (!(Test-Path $BACKEND)) {
  Write-Host "找不到 backend 資料夾：$BACKEND" -ForegroundColor Red
  Pause
  exit 1
}

Set-Location $BACKEND

if (!(Test-Path $VENV_ACT)) {
  Write-Host "找不到 venv：$VENV_ACT" -ForegroundColor Red
  Write-Host "你可能還沒建立 .venv，或 .venv 不在 backend 內。" -ForegroundColor Red
  Pause
  exit 1
}

. $VENV_ACT

# 用 start 開新視窗跑 uvicorn，避免這個視窗卡死
$cmd = 'python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000'
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$BACKEND`"; . `"$VENV_ACT`"; $cmd" | Out-Null

Write-Host "FastAPI 已在新視窗啟動（port 8000）。" -ForegroundColor Green

# ===== 3) 開啟瀏覽器 =====
Write-Host "`n[3/3] 開啟 Swagger..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
Start-Process "http://127.0.0.1:8000/docs"

Write-Host "`n✅ 完成！" -ForegroundColor Cyan
Write-Host "店內客人掃 QRCode 用：http://<你的電腦IP>:8000/track/<token>" -ForegroundColor DarkGray
Write-Host "（例如你之前那個）http://192.168.0.202:8000/track/D3B8F5FF" -ForegroundColor DarkGray

Pause
