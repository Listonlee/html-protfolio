"""集中讀取設定(由 .env)。所有 module 都由呢度攞 config。"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "leadgen.db"

# ── 爬文 ──
SCRAPER_PROVIDER = os.getenv("SCRAPER_PROVIDER", "mock").lower()
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
APIFY_ACTOR = os.getenv("APIFY_ACTOR", "apify/threads-scraper")

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
