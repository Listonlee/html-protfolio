#!/usr/bin/env bash
# 本機一鍵啟動(Mac / Linux)。
set -e
cd "$(dirname "$0")"

# 出錯時停低,等你睇到錯誤(double-click 嘅 Terminal 唔會即閂)
trap 'echo; echo "⚠️  出咗錯。將上面嘅文字 copy 畀 Claude 幫你睇。"; read -p "撳 Enter 關閉…"' ERR

# 揀 python
PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
if ! command -v $PY >/dev/null 2>&1; then
  echo "❌ 搵唔到 Python。請先去 https://www.python.org/downloads/ 裝 Python 3,裝完再試一次。"
  read -p "撳 Enter 關閉…"; exit 1
fi
echo "✓ 用緊 $($PY --version)"

echo "▶ 1/4 安裝依賴(第一次可能要等幾分鐘)…"
$PY -m pip install -q -r requirements.txt

if [ ! -f .env ]; then
  echo "▶ 建立 .env(預設 mock + SQLite,唔使任何 key)"
  cp .env.example .env
fi

echo "▶ 2/4 初始化資料庫 + 建立管理員…"
$PY -m scripts.seed

echo "▶ 3/4 載入樣本資料(mock 爬文 + 分析)…"
$PY -m scripts.run_pipeline

echo ""
echo "============================================================"
echo "  ▶ 4/4 Server 開緊… 跟住請做:"
echo "    1) 開瀏覽器入:  http://localhost:8000"
echo "    2) 登入:you@example.com / change-this-strong-password"
echo "    3) 試完喺呢度撳 Ctrl+C 停止(呢個視窗唔好閂)"
echo "============================================================"
echo ""
$PY -m uvicorn app.main:app --host 127.0.0.1 --port 8000
