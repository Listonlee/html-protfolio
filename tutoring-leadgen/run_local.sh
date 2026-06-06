#!/usr/bin/env bash
# 本機一鍵啟動(Mac / Linux)。喺 tutoring-leadgen/ 資料夾跑:  ./run_local.sh
set -e

cd "$(dirname "$0")"

# 揀 python
PY=python3
command -v $PY >/dev/null 2>&1 || PY=python

echo "▶ 1/4 安裝依賴…"
$PY -m pip install -q -r requirements.txt

if [ ! -f .env ]; then
  echo "▶ 建立 .env(預設 mock + SQLite,唔使任何 key)"
  cp .env.example .env
fi

echo "▶ 2/4 初始化資料庫 + 建立管理員…"
$PY -m scripts.seed

echo "▶ 3/4 載入樣本資料(mock 爬文 + 分析)…"
$PY -m scripts.run_pipeline

echo "▶ 4/4 開 server → http://localhost:8000"
echo "   登入用 .env 入面嘅 ADMIN_EMAIL / ADMIN_PASSWORD"
echo "   (預設 you@example.com / change-this-strong-password)"
echo "   按 Ctrl+C 停止。"
$PY -m uvicorn app.main:app --host 127.0.0.1 --port 8000
