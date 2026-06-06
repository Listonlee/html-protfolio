@echo off
REM 本機一鍵啟動(Windows)。喺 tutoring-leadgen 資料夾 double-click 或喺 cmd 跑:run_local.bat
cd /d "%~dp0"

echo [1/4] 安裝依賴...
python -m pip install -q -r requirements.txt

if not exist .env (
  echo 建立 .env ^(預設 mock + SQLite^)
  copy .env.example .env
)

echo [2/4] 初始化資料庫 + 建立管理員...
python -m scripts.seed

echo [3/4] 載入樣本資料...
python -m scripts.run_pipeline

echo [4/4] 開 server -^> http://localhost:8000
echo    登入用 .env 入面嘅 ADMIN_EMAIL / ADMIN_PASSWORD
echo    ^(預設 you@example.com / change-this-strong-password^)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
