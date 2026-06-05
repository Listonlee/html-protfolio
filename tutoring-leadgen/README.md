# 補習主動搵客工具 — 團隊 Web App

監察 Threads → AI 識別「搵緊補習」嘅人(避開同行)→ 入庫 →
團隊登入,喺審核台**半自動**跟進(AI 出草稿,你 review、複製、親自發送)。

> **架構**:FastAPI + Jinja2(一個 container)・ SQLAlchemy(本機 SQLite / 上雲 Postgres)・ 認證(email + 密碼 + 角色)
> **部署**:Docker → Google Cloud Run。詳細步驟見 [`DEPLOY.md`](DEPLOY.md)。
> **半自動**:工具負責搵客 + 草擬,**唔會自動 post**(避封號),最後一步團隊親自發。

## 本機快速試(唔使任何 key)

```bash
cd tutoring-leadgen
pip install -r requirements.txt
cp .env.example .env          # 預設 mock + SQLite,唔使填 key

python -m scripts.seed        # 建立管理員 + 範例資料(讀 .env 嘅 ADMIN_*)
python -m scripts.run_pipeline  # 爬(樣本)→ 分析 → 入庫
uvicorn app.main:app --reload   # 開 http://localhost:8000
```

瀏覽器入 `http://localhost:8000` → 用 `.env` 裏 `ADMIN_EMAIL` / `ADMIN_PASSWORD` 登入。

## 功能

- **登入認證**:email + 密碼(pbkdf2 雜湊)、session cookie、角色(admin / member)。
- **審核台**:按 score 排序 leads;狀態 / 科目 / 搜尋 篩選;改草稿、重新生成、開原 post、揀回覆帳號、標記已發送 / 忽略。
- **帳號設定(admin)**:管理多個 **Threads 回覆帳號**(設預設)、**團隊成員**、**同行黑名單**。
- **分析**:意圖分佈、熱門科目、發送率。
- **立即爬文**:admin 可喺審核台一鍵觸發 pipeline。

## 角色

| 角色 | 可做 |
|------|------|
| **admin**(主帳號) | 全部:審核、管理 Threads 帳號 / 團隊成員 / 黑名單、觸發爬文 |
| **member**(團隊成員) | 審核 leads、回覆、睇分析 |

## Provider 切換(改 `.env` / 環境變數)

| | mock(預設) | 真 |
|---|---|---|
| 爬文 | 內置樣本 | `SCRAPER_PROVIDER=apify` + `APIFY_API_TOKEN` |
| LLM | 關鍵詞啟發式 | `LLM_PROVIDER=gemini` + `GEMINI_API_KEY`(或 `openrouter`) |

## 排程(每日自動爬)

兩種方式:
1. **Cloud Scheduler** → `POST /tasks/run`,帶 header `X-Pipeline-Token: <PIPELINE_TOKEN>`(見 DEPLOY.md)。
2. 本機 cron:`python -m scripts.run_pipeline`。

## 結構

```
app/
├── main.py            # FastAPI 路由(登入 / 審核 / 帳號 / 觸發)
├── config.py          # 環境變數設定
├── database.py        # SQLAlchemy 引擎(SQLite / Postgres)
├── models.py          # User / ThreadsAccount / Competitor / Post / Analysis / Reply
├── auth.py            # 密碼雜湊 + session 守衛
├── crud.py            # DB 操作
├── services/
│   ├── scraper.py     # mock / apify
│   ├── llm.py         # mock / gemini / openrouter
│   └── pipeline.py    # 爬→分析→入庫
├── templates/         # login / dashboard / analytics / accounts
└── static/style.css
scripts/
├── seed.py            # 建立管理員 + 範例資料
└── run_pipeline.py    # CLI 觸發 pipeline(cron 用)
tests/test_logic.py    # 核心邏輯測試
Dockerfile             # Cloud Run 部署
```

## 測試

```bash
python -m tests.test_logic
```

## ⚠️ 注意

- 爬文可能違反平台 ToS,自行評估;低頻使用。
- **唔自動 post**:確認後請親自去原 post 回覆。
- `.env` / `*.db` 已 gitignore。部署用嘅 secret 放 Cloud Run 環境變數 / Secret Manager,唔好入 git。
