# 補習主動搵客工具 — 技術方案 / Design Doc

> 目標:每日監察 **Threads (Meta)** 上嘅 post,用 AI 識別「同學生 / 補習有關」嘅內容,
> 特別係「問補某科邊個好 / 搵緊補習老師」嘅人,然後用預設賬號**半自動**回覆,主動搵客;
> 同時避免回覆到同行(競爭對手)嘅 post。

- **平台**:Threads (Meta)
- **回覆模式**:半自動(AI 寫草稿 → 人手 review → 一鍵發送)
- **狀態**:設計階段(本文件),未寫實際 code

---

## 1. 整體架構

```
                    ┌─────────────────────────────────────────────┐
                    │              每日排程 (Scheduler)             │
                    │   GitHub Actions cron / Apify Scheduler      │
                    └───────────────────────┬─────────────────────┘
                                            │ 觸發
                                            ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ [1] 爬文      │ ──▶ │ [2] 清洗去重  │ ──▶ │ [3] AI 分析   │ ──▶ │ [4] Database │
│ Apify Threads│     │ Normalize +  │     │ Claude API   │     │ Postgres /   │
│ Scraper      │     │ Dedup        │     │ (Haiku)      │     │ Supabase     │
└──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                       │
                                            ┌──────────────────────────┘
                                            ▼
                    ┌──────────────────────────────────────────────┐
                    │ [5] 審核後台 (Review Dashboard)                │
                    │  - 睇 leads(按 lead_score 排序)             │
                    │  - 睇 AI 草擬回覆                              │
                    │  - 一鍵「發送」/「忽略」/「改稿」             │
                    └───────────────────────┬──────────────────────┘
                                            │ 確認發送
                                            ▼
                    ┌──────────────────────────────────────────────┐
                    │ [6] 回覆發送 (Reply Sender)                    │
                    │  - Threads 官方 API(回覆自己被 reply)        │
                    │  - 或 Apify post actor(風險較高)            │
                    │  - Rate limit + 隨機 delay                    │
                    └──────────────────────────────────────────────┘
```

---

## 2. 每個 Component 詳解

### [1] 爬文 (Data Ingestion)

**問題核心:Threads 冇開放「搜尋/讀取其他人 post」嘅官方 API。**

Threads 官方 API(`graph.threads.net`)目前只支援:
- 發佈自己賬號嘅 post
- 讀取 / 回覆**自己 post 底下**嘅 replies
- 攞自己賬號嘅 insights

要監察「其他人」嘅 post,得靠第三方爬蟲:

- **建議用 Apify**,現成 actor(例如 `Threads Scraper`),可以:
  - 按 **keyword / hashtag** 搜尋(例:`補習`、`補數學`、`搵補習`、`DSE 補習`、`#補習`)
  - 按特定賬號嘅 timeline 爬
- 輸出:post 文字、作者 handle、post URL、時間、likes/replies 數。

**反爬與 ToS 注意:**
- Threads 反爬較嚴,Apify actor 內部會處理 proxy / rotation,但仍可能間中 fail → 要做 retry + 監控。
- 爬文本身可能違反平台 ToS,屬法律灰色地帶,須自行評估。
- 控制頻率(每日一次 / 每幾粒鐘),唔好過密。

**Keyword 策略(初版)**

| 類別 | 關鍵詞範例 |
|------|-----------|
| 直接搵補習 | 搵補習、補習老師、邊個補得好、求補習、揾 tutor |
| 科目 | 補數學、補英文、補中文、補 physics、DSE、IB、補 phonics |
| 程度 | 小學補習、中學補習、升小一、呈分試、文憑試 |

### [2] 清洗 + 去重 (Normalize & Dedup)

- 用 `post_id` 做 unique key,避免重複處理 / 重複回覆(**最重要**)。
- 去除 emoji 噪音、normalize 空白、截斷過長內容(慳 token)。
- 過濾明顯廣告 / bot post(初步 rule-based,再交 AI 細判)。

### [3] AI 分析 (Intent Classification) — 核心

用 **Anthropic Claude API**。大量 post 分類用 **`claude-haiku-4-5`**(快、平);
遇到模棱兩可先 escalate 去 `claude-sonnet-4-6`。

用 **tool use(structured output）** 強制 model 輸出固定 JSON schema:

```json
{
  "is_tutoring_related": true,
  "intent": "looking_for_tutor",
  "subject": "中學數學",
  "level": "中四",
  "region": "九龍",
  "is_competitor": false,
  "is_advertisement": false,
  "lead_score": 0.86,
  "reason": "用戶問緊邊個補中四數學好,有明確需求",
  "suggested_reply": "你好~我哋有專補中四數學嘅老師..."
}
```

**`intent` 枚舉值:**
- `looking_for_tutor` — 搵緊補習(★ 目標客)
- `selling_tutoring` — 賣補習服務(★ 同行,要避開)
- `discussion` — 純討論 / 分享,冇即時需求
- `not_related` — 同補習無關

**避開同行邏輯:**
- `is_competitor` / `intent == selling_tutoring` → **唔回覆**。
- 同行特徵:自我推銷語氣、留電話/WhatsApp、有 hashtag spam、係 tutoring agency 賬號。
- 可額外維護一個「已知同行 handle 黑名單」。

**只回覆嘅條件(建議):**
```
is_tutoring_related == true
AND intent == "looking_for_tutor"
AND is_competitor == false
AND is_advertisement == false
AND lead_score >= 0.7
```

### [4] Database

建議 **Supabase (Postgres)** — 有免費 tier,連埋 auth、auto REST API,啱做後台。

**Schema(初版):**

```sql
-- 原始爬到嘅 post
CREATE TABLE posts (
  id            BIGINT PRIMARY KEY,        -- internal
  platform      TEXT NOT NULL DEFAULT 'threads',
  post_id       TEXT UNIQUE NOT NULL,      -- 平台 post id,做去重
  author_handle TEXT,
  content       TEXT,
  url           TEXT,
  posted_at     TIMESTAMPTZ,
  scraped_at    TIMESTAMPTZ DEFAULT now()
);

-- AI 分析結果
CREATE TABLE analysis (
  id              BIGINT PRIMARY KEY,
  post_id         TEXT REFERENCES posts(post_id),
  is_tutoring     BOOLEAN,
  intent          TEXT,
  subject         TEXT,
  level           TEXT,
  is_competitor   BOOLEAN,
  lead_score      NUMERIC,
  suggested_reply TEXT,
  model           TEXT,
  analyzed_at     TIMESTAMPTZ DEFAULT now()
);

-- 回覆狀態
CREATE TABLE replies (
  id           BIGINT PRIMARY KEY,
  post_id      TEXT REFERENCES posts(post_id),
  status       TEXT DEFAULT 'pending',     -- pending/approved/sent/ignored/failed
  final_reply  TEXT,
  reviewed_by  TEXT,
  sent_at      TIMESTAMPTZ
);
```

### [5] 審核後台 (Review Dashboard) — 半自動關鍵

因為你揀咗**半自動**,呢個後台係必須嘅。

- **最快做法**:Streamlit / Retool(內部用,幾粒鐘搞掂)。
- **正式做法**:Next.js + Supabase。
- 功能:
  - 列出 `status = pending` 且符合回覆條件嘅 leads,按 `lead_score` 排序。
  - 每個 lead 顯示:原 post、AI 判斷理由、AI 草擬回覆(可編輯)。
  - 三個按鈕:**發送 / 改稿後發送 / 忽略**。
  - 顯示每日已發送數,提你唔好超 rate limit。

### [6] 回覆發送 (Reply Sender)

⚠️ **最敏感、最易封號嘅一步。**

- Threads 官方 API **唔俾你主動 reply 任意 post**(只可以回自己 post 底下嘅 comment)。
- 所以「主動去人哋 post 底下留言」基本上要靠**模擬登入 / Apify 自動化**,呢個明確踩 ToS,封號風險高。
- **降風險措施(必做):**
  - Rate limit:每日上限(例如 10–20 條),隨機 delay(幾分鐘到幾十分鐘)。
  - 內容多樣化,唔好每次 copy-paste 同一句(會被當 spam)。
  - 用 warm-up 過嘅賬號,唔好新號就狂 post。
  - 一定保留 human-in-the-loop,唔好全自動。

> **替代策略(更安全、更合規):**
> 與其去人哋 post 底下硬回覆,不如**自己賬號定期發優質內容**(免費補習 tips / 答題),
> 吸引有需要嘅人主動 reply / DM 你。再用官方 API 管理自己 post 底下嘅 replies(完全合規)。
> 監察工具就純粹用嚟「搵到有需求嘅人」+「分析市場關鍵詞」,回覆改成人手 DM。

### [7] 排程 (Scheduler)

- **GitHub Actions** `schedule` cron(免費,啱輕量)。
- 或 **Apify Scheduler**(同 scraper 一齊管)。
- 建議每日 1–2 次,避免過密。

---

## 3. 技術 Stack 總結

| 層 | 選型 | 備註 |
|----|------|------|
| 語言 | Python 3.11+ | 爬蟲 + AI 生態最齊 |
| 爬文 | Apify Threads Scraper | 慳反爬功夫 |
| AI | Anthropic Claude API (`claude-haiku-4-5` 主力) | structured output via tool use |
| DB | Supabase (Postgres) | 免費 tier + auto API |
| 後台 | Streamlit(MVP)/ Next.js(正式) | 半自動審核 |
| 排程 | GitHub Actions cron | 免費 |
| Secrets | `.env` / GitHub Secrets | API key 唔好入 git |

---

## 4. 成本概念(粗略)

- **Apify**:按 actor 用量計,有免費額度,輕量監察每月幾美金級。
- **Claude (Haiku)**:每條 post 分類成本極低(input+output 細),每日幾百條都係幾美仙。
- **Supabase**:免費 tier 通常夠用。
- 主要成本反而係**封號 / 帳號維護**嘅隱性風險。

---

## 5. 風險與合規(必讀)

1. **平台 ToS**:爬文 + 自動回覆通常違反 Threads/Meta 條款 → 封號、甚至法律風險。
2. **Spam 觀感**:硬 cold-comment 易招反感,傷品牌。建議走「內容吸引 + 人手 DM」更穩。
3. **私隱**:存到第三方用戶資料(handle/內容),注意 PDPO / 唔好濫用。
4. **可靠性**:第三方爬蟲會 break(平台改版),要有 retry + 失敗通知。

---

## 6. 建議落地步驟(Roadmap)

1. **Phase 0 — 唯讀驗證**:先淨係爬 + AI 分類 + 入庫,睇下每日真係搵到幾多個 lead、準唔準。**唔回覆。**
2. **Phase 1 — 審核後台**:加 Streamlit dashboard,人手睇 leads + 手動 DM 跟進。
3. **Phase 2 — 半自動回覆**:確認 lead 質素 OK 之後,先加「一鍵發送」+ rate limit。
4. **Phase 3 — 優化**:keyword 調優、prompt 調優、加同行黑名單、加 analytics。

> 強烈建議由 Phase 0 開始,用真數據驗證「搵到客」嘅準確度,再決定使唔使冒封號風險去自動回覆。
