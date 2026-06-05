# 補習主動搵客工具 — MVP (Phase 0)

監察 Threads 上嘅 post → AI 識別「搵緊補習」嘅人(同時避開同行)→ 入庫 →
喺一個簡單 UI **半自動**審核(AI 出草稿,你 review 後親自發送)。

> 設計理念見 [`../docs/tutoring-lead-gen-design.md`](../docs/tutoring-lead-gen-design.md)。
> **半自動** = 工具只負責搵客 + 草擬,**唔會自動 post**(避封號),最後一步由你親自發。

## 即刻試(唔使任何 API key)

```bash
cd tutoring-leadgen
pip install -r requirements.txt
cp .env.example .env          # 預設 mock 模式,唔使填 key

python pipeline.py            # 爬(樣本)→ 分析 → 入庫
streamlit run app.py          # 開審核 UI
```

mock 模式用內置樣本 post + 關鍵詞啟發式分類,等你即刻見到成個流程點 work。

## 接真數據(填 key 就轉)

改 `.env`:

```ini
# 真係爬 Threads
SCRAPER_PROVIDER=apify
APIFY_API_TOKEN=你的_token

# 用 Google Gemini 分析
LLM_PROVIDER=gemini
GEMINI_API_KEY=你的_key

# 將來轉 OpenRouter:淨係改呢三行,prompt/schema 都唔使郁
# LLM_PROVIDER=openrouter
# OPENROUTER_API_KEY=...
# OPENROUTER_MODEL=google/gemini-2.0-flash-001
```

Gemini 同 OpenRouter 都行 OpenAI-compatible API,所以轉 provider 只係換
base_url / key / model(已喺 `config.py` 處理好)。

## 檔案結構

| 檔案 | 作用 |
|------|------|
| `config.py` | 讀 `.env`,集中設定 |
| `scraper.py` | 爬文層(`mock` / `apify`),統一 `fetch_posts()` |
| `llm.py` | LLM 分析層(`mock` / `gemini` / `openrouter`),統一 `analyze_post()` |
| `db.py` | SQLite:posts / analysis / replies 三張表 + 去重 |
| `pipeline.py` | 每日跑:爬 → 去重 → 分析 → 入庫 |
| `app.py` | Streamlit 半自動審核 UI |

## 搵客 / 避同行邏輯

一條 post 會喺 dashboard 出現,當且僅當:

```
is_tutoring_related == true
AND intent == "looking_for_tutor"      # 搵緊補習(唔係賣補習)
AND is_competitor == false             # 避開同行
AND is_advertisement == false
AND lead_score >= LEAD_SCORE_THRESHOLD # 預設 0.7
```

## 每日自動跑(可選)

本機 crontab 例子(每日 9am 爬一次):

```cron
0 9 * * * cd /path/to/tutoring-leadgen && /usr/bin/python3 pipeline.py >> cron.log 2>&1
```

跑完之後你開 `streamlit run app.py` 審核當日 leads 就得。

## ⚠️ 注意

- 爬文可能違反平台 ToS,自行評估風險;建議低頻、唔好濫用。
- MVP **唔自動 post**:確認後請複製草稿,親自去原 post 回覆。
- `.env` / `*.db` 已 gitignore,唔好 commit key 同數據。
