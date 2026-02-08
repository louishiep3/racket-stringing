@echo off
cd /d %~dp0

echo =============================
echo   昇活穿線系統 啟動中...
echo =============================

REM 啟動 Docker DB
docker compose up -d

REM 啟動 FastAPI
start powershell -NoExit -Command ^
"cd backend; .\.venv\Scripts\Activate.ps1; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

REM 打開 Swagger
timeout /t 2 >nul
start http://127.0.0.1:8000/docs

echo.
echo 完成！
pause
