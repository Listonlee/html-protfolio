"""集中設定（由環境變數 / .env 讀取）。

本機:由 .env 讀。
Cloud Run:由 service 嘅環境變數讀(唔使 .env)。
"""
import os

from dotenv import load_dotenv

load_dotenv()  # 本機方便;Cloud Run 上冇 .env 都唔會報錯


def _bool(v: str) -> bool:
    return str(v).lower() in ("1", "true", "yes", "on")


# ── 資料庫 ──
# 本機預設 SQLite;上雲設成 Postgres 連線字串,例如:
#   postgresql+psycopg2://USER:PASSWORD@HOST:5432/postgres
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./leadgen.db")

# ── Session / 安全 ──
# 部署前一定要設一個夠長嘅隨機字串(下面有教點 gen)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-change-me")
# Cloud Run 行 HTTPS,設 true 令 cookie 只行加密連線
COOKIE_SECURE = _bool(os.getenv("COOKIE_SECURE", "false"))

# ── 首個管理員(seed 用)──
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme123")

# ── 爬文 ──
SCRAPER_PROVIDER = os.getenv("SCRAPER_PROVIDER", "mock").lower()
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
APIFY_ACTOR = os.getenv("APIFY_ACTOR", "apify/threads-scraper")
RESULTS_LIMIT = int(os.getenv("RESULTS_LIMIT", "100"))
SEARCH_KEYWORDS = [
    k.strip()
    for k in os.getenv("SEARCH_KEYWORDS", "補習,搵補習,補數學,補英文,DSE補習,補習老師").split(",")
    if k.strip()
]

# ── LLM ──
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ── 搵客條件 ──
LEAD_SCORE_THRESHOLD = float(os.getenv("LEAD_SCORE_THRESHOLD", "0.7"))

# ── 觸發 pipeline 用嘅密鑰(畀 Cloud Scheduler 呼叫 /tasks/run)──
PIPELINE_TOKEN = os.getenv("PIPELINE_TOKEN", "")


def validate() -> list[str]:
    warnings = []
    if SECRET_KEY == "dev-insecure-change-me":
        warnings.append("SECRET_KEY 仲係預設值,部署前必須改")
    if SCRAPER_PROVIDER == "apify" and not APIFY_API_TOKEN:
        warnings.append("SCRAPER_PROVIDER=apify 但 APIFY_API_TOKEN 係空")
    if LLM_PROVIDER == "gemini" and not GEMINI_API_KEY:
        warnings.append("LLM_PROVIDER=gemini 但 GEMINI_API_KEY 係空")
    if LLM_PROVIDER == "openrouter" and not OPENROUTER_API_KEY:
        warnings.append("LLM_PROVIDER=openrouter 但 OPENROUTER_API_KEY 係空")
    return warnings
