# 部署指南 — 放上網俾團隊用

呢份文件教你由零將個 web app 部署上網,團隊登入即用(非公開)。
跟住做就得,唔需要太多技術底。

---

## 一、Infrastructure 用咩?(我嘅建議)

| 部分 | 用咩 | 點解 | 費用 |
|------|------|------|------|
| **網站主機** | **Google Cloud Run** | 容器化、自動擴縮、唔使管 server、有免費額度 | 細用量幾乎免費(每月有 200 萬 request 免費額度) |
| **資料庫** | **Supabase(Postgres)** | 託管 Postgres、有免費 tier、易上手 | 免費 tier 夠團隊用 |
| **AI** | **Google Gemini API** | 你已有方向、Flash 平、夠快 | 極低,有免費額度 |
| **爬文** | **Apify**(Threads actor) | 慳反爬功夫 | 有免費 credit |
| **排程** | **Cloud Scheduler** | 每日自動爬 | 免費額度足夠 |
| **密碼/Token** | Cloud Run 環境變數(或 Secret Manager) | 唔好入 git | 免費 |

> **點解唔用 Streamlit?** Streamlit 做唔到正經多用戶登入 / 角色 / 帳號管理。
> 而家改用 FastAPI,係一個正規 web app,啱團隊長期用。

整體:**一個 Cloud Run service(個 app)+ 一個 Supabase Postgres(資料)+ 一個 Cloud Scheduler(每日爬)**。

---

## 二、開始前你要準備(我需要 / 你要攞嘅嘢)

> 呢部分就係你問「仲欠咩資料」嘅答案。Collect 齊就部署到。

### 一定要
1. **一個 Google 帳號**(用嚟開 Google Cloud)。
2. **信用卡**(Google Cloud 要綁卡先啟用,但有免費額度,細用量唔會扣錢)。
3. **Gemini API key** — 去 https://aistudio.google.com → Get API key。
4. **Apify API token** — 去 https://apify.com 註冊 → Settings → Integrations → API token。
5. **揀定一隻 Threads scraper actor** — Apify Store 搜「Threads」,揀支援關鍵詞搜尋嗰隻,記低佢個 actor id(例如 `someuser/threads-scraper`)。
6. **管理員 email + 密碼** — 你想用嚟登入主帳號嘅(自己定)。
7. **團隊成員名單** — 之後喺 app 裏面加(email + 密碼),呢個唔使部署前準備。

### 要決定
- **關鍵詞**:監察邊啲字(預設:補習、搵補習、補數學、補英文、DSE補習、補習老師)。
- **同行黑名單**:已知同行 handle(部署後喺 app 加都得)。
- **回覆語氣**:之後可以再調 prompt。

---

## 三、Step 1:整定 Database(Supabase)

1. 去 https://supabase.com → 用 GitHub / Google 登入 → **New project**。
2. 改個 project 名、設一個 **database password**(記低佢)。
3. 等佢 build 好(約 1 分鐘）。
4. 去 **Project Settings → Database → Connection string → URI**,copy 條連線字串,類似:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```
5. 將開頭改成 SQLAlchemy 格式(加 `+psycopg2`):
   ```
   postgresql+psycopg2://postgres:你的密碼@db.xxxxx.supabase.co:5432/postgres
   ```
   呢條就係之後要填嘅 **`DATABASE_URL`**。

> 表會喺 app 第一次啟動時自動建立(唔使你手動開表）。

---

## 四、Step 2:準備 secret 值

1. **產生 SECRET_KEY**(本機 / 任何有 python 嘅地方跑):
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   copy 個輸出。
2. **產生 PIPELINE_TOKEN**(排程觸發用,同上方法再跑一次)。

你而家應該有齊呢堆值:
- `DATABASE_URL`(Supabase)
- `SECRET_KEY`、`PIPELINE_TOKEN`
- `ADMIN_EMAIL`、`ADMIN_PASSWORD`
- `GEMINI_API_KEY`、`APIFY_API_TOKEN`、`APIFY_ACTOR`

---

## 五、Step 3:部署上 Cloud Run

### 裝 gcloud(一次性)
- 跟 https://cloud.google.com/sdk/docs/install 裝 `gcloud` CLI。
- 然後:
  ```bash
  gcloud auth login
  gcloud projects create tutoring-leadgen-xxxx   # 或喺 console 開好 project
  gcloud config set project tutoring-leadgen-xxxx
  gcloud services enable run.googleapis.com cloudbuild.googleapis.com
  ```

### 部署(一條 command)
喺 `tutoring-leadgen/` 資料夾(有 Dockerfile 嗰個)跑:

```bash
gcloud run deploy tutoring-leadgen \
  --source . \
  --region asia-east1 \
  --allow-unauthenticated \
  --set-env-vars "DATABASE_URL=postgresql+psycopg2://postgres:密碼@db.xxx.supabase.co:5432/postgres" \
  --set-env-vars "SECRET_KEY=你產生嘅,COOKIE_SECURE=true" \
  --set-env-vars "ADMIN_EMAIL=you@example.com,ADMIN_PASSWORD=你的強密碼" \
  --set-env-vars "PIPELINE_TOKEN=你產生嘅" \
  --set-env-vars "SCRAPER_PROVIDER=apify,APIFY_API_TOKEN=xxx,APIFY_ACTOR=someuser/threads-scraper" \
  --set-env-vars "LLM_PROVIDER=gemini,GEMINI_API_KEY=xxx" \
  --set-env-vars "SEARCH_KEYWORDS=補習,搵補習,補數學,補英文,DSE補習"
```

> - `--allow-unauthenticated` 係指「Cloud Run 層面唔擋」,**真正嘅保護係 app 自己嘅登入頁**(團隊要 email/密碼先入到)。
> - `--source .` 會自動用 Dockerfile build image,唔使你手動 build。
> - 完成後會 print 一條 `https://tutoring-leadgen-xxxx.a.run.app` —— **呢條就係你團隊嘅網址**。

### 第一次登入
- 開條 Cloud Run URL → 用你設嘅 `ADMIN_EMAIL` / `ADMIN_PASSWORD` 登入。
- 入「⚙️ 帳號設定」→ 加團隊成員、加 Threads 回覆帳號、加同行黑名單。

---

## 六、Step 4:每日自動爬(Cloud Scheduler)

```bash
gcloud services enable cloudscheduler.googleapis.com

gcloud scheduler jobs create http tutoring-daily-scrape \
  --location asia-east1 \
  --schedule "0 9 * * *" \
  --uri "https://tutoring-leadgen-xxxx.a.run.app/tasks/run" \
  --http-method POST \
  --headers "X-Pipeline-Token=你的_PIPELINE_TOKEN" \
  --time-zone "Asia/Hong_Kong"
```

每日 9am 自動爬一次。團隊登入入審核台就見到當日 leads。

---

## 七、更新 app(改完 code 之後)

```bash
git pull   # 攞最新 code
gcloud run deploy tutoring-leadgen --source . --region asia-east1
```

環境變數會保留,唔使再填。

---

## 八、費用控制 tips

- Cloud Run 設 **min instances = 0**(預設),冇人用就唔收錢。
- Supabase / Gemini / Apify 都有免費額度,細團隊用量基本免費。
- 想封頂:Cloud Run 設 `--max-instances 2`、Apify 設用量上限。

---

## 九、安全 checklist(部署前)

- [ ] `SECRET_KEY` 已換成隨機值(唔好用預設)
- [ ] `COOKIE_SECURE=true`(Cloud Run 行 HTTPS)
- [ ] `ADMIN_PASSWORD` 夠強
- [ ] secret 全部用環境變數,冇 commit 入 git
- [ ] `PIPELINE_TOKEN` 已設(防止有人亂觸發爬文)

---

## 仲有咩唔清楚?

部署任何一步卡住,將錯誤訊息貼返出嚟,我可以逐步幫你 debug。
如果你想用其他主機(例如 Render、Railway、Fly.io),都得 —— 個 app 係標準 Docker container,話我知我畀返對應步驟。
