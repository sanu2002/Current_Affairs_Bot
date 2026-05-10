# ============================================================
#  config.py — Central settings
# ============================================================
import os
from dotenv import load_dotenv
load_dotenv()

# ── Credentials ───────────────────────────────────────────
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY",  "YOUR_ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "@your_channel")

# ── Model ─────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ── Schedule ──────────────────────────────────────────────
SEND_TIME         = "08:00"   # 24h HH:MM (IST)
QUESTIONS_PER_DAY = 15        # 10–20

# ── Backfill range ────────────────────────────────────────
BACKFILL_START = "2026-01-01"   # Jan 2026 → today

# ── RSS feeds  (ongoing daily news — recent ~30 days) ─────
RSS_FEEDS = [
    "https://pib.gov.in/RssMain.aspx?ModID=6&Lang=1",
    "https://www.thehindu.com/news/national/feeder/default.rss",
    "https://www.thehindu.com/sci-tech/science/feeder/default.rss",
    "https://www.thehindu.com/business/Economy/feeder/default.rss",
    "https://indianexpress.com/section/india/feed/",
    "https://indianexpress.com/section/explained/feed/",
    "https://ddnews.gov.in/feed/",
    "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
]

# ── DB ────────────────────────────────────────────────────
DB_PATH = "bot_data.db"
