"""集中讀取設定(由 .env)+ logging + 設定驗證。
所有 module 都由呢度攞 config。
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "leadgen.db"
COMPETITORS_FILE = BASE_DIR / "competitors.txt"

# ── 爬文 ──
SCRAPER_PROVIDER = os.getenv("SCRAPER_PROVIDER", "mock").lower()
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
APIFY_ACTOR = os.getenv("APIFY_ACTOR", "apify/threads-scraper")
RESULTS_LIMIT = int(os.getenv("RESULTS_LIMIT", "100"))

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

# ── 關鍵詞 ──
SEARCH_KEYWORDS = [
    k.strip()
    for k in os.getenv("SEARCH_KEYWORDS", "補習,搵補習,補數學").split(",")
    if k.strip()
]

# ── Logging ──
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("leadgen")


def load_competitors() -> set[str]:
    """讀同行黑名單(competitors.txt,一行一個 handle,# 開頭係註解)。
    比較時統一去掉 @ 同轉細楷。"""
    if not COMPETITORS_FILE.exists():
        return set()
    out = set()
    for line in COMPETITORS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line.lstrip("@").lower())
    return out


def add_competitor(handle: str):
    handle = handle.strip().lstrip("@")
    if not handle:
        return
    existing = load_competitors()
    if handle.lower() in existing:
        return
    with open(COMPETITORS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{handle}\n")


def validate() -> list[str]:
    """檢查設定有冇明顯問題,回傳一串警告訊息(空 = OK)。"""
    warnings = []
    if SCRAPER_PROVIDER not in ("mock", "apify"):
        warnings.append(f"SCRAPER_PROVIDER 未知值:{SCRAPER_PROVIDER}")
    if SCRAPER_PROVIDER == "apify" and not APIFY_API_TOKEN:
        warnings.append("SCRAPER_PROVIDER=apify 但 APIFY_API_TOKEN 係空")
    if LLM_PROVIDER not in ("mock", "gemini", "openrouter"):
        warnings.append(f"LLM_PROVIDER 未知值:{LLM_PROVIDER}")
    if LLM_PROVIDER == "gemini" and not GEMINI_API_KEY:
        warnings.append("LLM_PROVIDER=gemini 但 GEMINI_API_KEY 係空")
    if LLM_PROVIDER == "openrouter" and not OPENROUTER_API_KEY:
        warnings.append("LLM_PROVIDER=openrouter 但 OPENROUTER_API_KEY 係空")
    if not (0 <= LEAD_SCORE_THRESHOLD <= 1):
        warnings.append(f"LEAD_SCORE_THRESHOLD 應喺 0~1:{LEAD_SCORE_THRESHOLD}")
    if not SEARCH_KEYWORDS:
        warnings.append("SEARCH_KEYWORDS 係空")
    return warnings
