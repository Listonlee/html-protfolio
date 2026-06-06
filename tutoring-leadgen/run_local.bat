@echo off
REM 本機一鍵啟動(Windows)。喺資料夾 double-click 呢個 file 就得。
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo X 搵唔到 Python。請先去 https://www.python.org/downloads/ 裝 Python 3,
  echo   安裝時記得剔「Add Python to PATH」,裝完再 double-click 一次。
  pause
  exit /b 1
)

echo [1/4] 安裝依賴 (第一次可能要等幾分鐘)...
python -m pip install -q -r requirements.txt
if errorlevel 1 ( echo X 安裝依賴失敗,將上面文字 copy 畀 Claude。 & pause & exit /b 1 )

if not exist .env (
  echo 建立 .env ^(預設 mock + SQLite^)
  copy .env.example .env >nul
)

echo [2/4] 初始化資料庫 + 建立管理員...
python -m scripts.seed
if errorlevel 1 ( echo X seed 失敗,將上面文字 copy 畀 Claude。 & pause & exit /b 1 )

echo [3/4] 載入樣本資料...
python -m scripts.run_pipeline

echo.
echo ============================================================
echo   [4/4] Server 開緊... 跟住請做:
echo     1^) 開瀏覽器入:  http://localhost:8000
echo     2^) 登入:you@example.com / change-this-strong-password
echo     3^) 試完喺呢度撳 Ctrl+C 停止 ^(呢個視窗唔好閂^)
echo ============================================================
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
