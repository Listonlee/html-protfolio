# 補習主動搵客工具 — MVP

監察 Threads 上嘅 post → AI 識別「搵緊補習」嘅人(同時避開同行)→ 入庫 →
喺一個審核 UI **半自動**跟進(AI 出草稿,你 review、複製、親自發送)。

> 設計理念見 [`../docs/tutoring-lead-gen-design.md`](../docs/tutoring-lead-gen-design.md)。
> **半自動** = 工具負責搵客 + 草擬,**唔會自動 post**(避封號),最後一步由你親自發。

## 即刻試(唔使任何 API key)

```bash
cd tutoring-leadgen
pip install -r requirements.txt
cp .env.example .env          # 預設 mock 模式,唔使填 key

python pipeline.py check      # 驗證設定 + 測連線
python pipeline.py run        # 爬(樣本)→ 分析 → 入庫
streamlit run app.py          # 開審核 UI
```

mock 模式用內置樣本 post + 關鍵詞啟發式分類,等你即刻見到成個流程點 work。

## CLI

| 指令 | 作用 |
|------|------|
| `python pipeline.py run` | 爬 → 去重 → 分析 → 入庫 |
| `python pipeline.py run --limit 20` | 只處理頭 20 條 |
| `python pipeline.py run --dry-run` | 只分析、唔入庫(試效果) |
| `python pipeline.py run --reanalyze` | 連已分析過嘅都重做 |
| `python pipeline.py check` | 驗證設定 + 測 Apify / LLM 連線 |
| `python pipeline.py stats` | 睇累計統計 + 意圖/科目分佈 |
| `python test_logic.py` | 跑核心邏輯測試(免 key) |

## 接真數據(填 key 就轉)

改 `.env`:

```ini
# 真係爬 Threads
SCRAPER_PROVIDER=apify
APIFY_API_TOKEN=你的_token
APIFY_ACTOR=apify/threads-scraper   # 換成你揀嗰隻 actor

# 用 Google Gemini 分析
LLM_PROVIDER=gemini
GEMINI_API_KEY=你的_key

# 將來轉 OpenRouter:淨係改呢三行,prompt/schema 都唔使郁
# LLM_PROVIDER=openrouter
# OPENROUTER_API_KEY=...
# OPENROUTER_MODEL=google/gemini-2.0-flash-001
```

填完跑 `python pipeline.py check` 確認爬文同 LLM 都通,先至 `run`。

> ⚠️ 唔同 Apify actor 嘅 output 欄位名可能唔同。`scraper.py` 嘅 `_map_item()`
> 已經有多個 fallback 欄位,但用真 actor 前最好對返佢嘅文件核實 mapping。

## 審核台功能(`streamlit run app.py`)

- **📋 審核**:按 score 排序嘅 leads;狀態 / 科目 / 搜尋 篩選;
  可改草稿、**一鍵複製**、**♻️ 重新生成**、**↗ 開原 post**、**✅ 已發送 / 🚫 忽略**。
- **📊 分析**:意圖分佈、熱門科目、發送率圖表。
- **⚙️ 設定**:睇目前設定、設定檢查、**管理同行黑名單**。

## 搵客 / 避同行邏輯

一條 post 會喺審核台出現,當且僅當:

```
is_tutoring_related == true
AND intent == "looking_for_tutor"      # 搵緊補習(唔係賣補習)
AND is_competitor == false             # 避開同行(AI + 黑名單雙重)
AND is_advertisement == false
AND lead_score >= LEAD_SCORE_THRESHOLD # 預設 0.7
```

避同行有**兩層**:AI 判斷 + `competitors.txt` handle 黑名單(黑名單會強制覆寫成同行)。

## 可靠性

- LLM / Apify 呼叫都有 **retry + exponential backoff**。
- 單條 post 分析失敗**唔會搞冧成個 run**(記低 error 繼續)。
- `post_id` 去重,重跑唔會重複處理 / 重複回覆。
- 所有欄位經 `_normalize()` 保證齊全,`lead_score` 夾喺 0~1。

## 每日自動跑(可選)

本機 crontab(每日 9am 爬一次):

```cron
0 9 * * * cd /path/to/tutoring-leadgen && /usr/bin/python3 pipeline.py run >> cron.log 2>&1
```

跑完開 `streamlit run app.py` 審核當日 leads。

## 檔案結構

| 檔案 | 作用 |
|------|------|
| `config.py` | 讀 `.env`、logging、設定驗證、黑名單 |
| `scraper.py` | 爬文層(`mock` / `apify`)+ retry + 欄位 mapping |
| `llm.py` | LLM 分析層(`mock` / `gemini` / `openrouter`)+ retry + schema 正規化 |
| `db.py` | SQLite:posts / analysis / replies + 去重 + 查詢/分析 |
| `pipeline.py` | CLI:`run` / `check` / `stats` |
| `app.py` | Streamlit 審核 UI(3 分頁) |
| `competitors.txt` | 同行黑名單 |
| `test_logic.py` | 核心邏輯測試 |

## ⚠️ 注意

- 爬文可能違反平台 ToS,自行評估風險;建議低頻、唔好濫用。
- **唔自動 post**:確認後請複製草稿,親自去原 post 回覆。
- `.env` / `*.db` 已 gitignore,唔好 commit key 同數據。
