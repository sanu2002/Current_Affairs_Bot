# ============================================================
#  news_fetcher.py — Agent 1: News Fetcher
#
#  TWO modes:
#   A) RSS   — for recent/ongoing daily news (last ~30 days)
#   B) SEARCH — uses Claude's web_search tool to retrieve
#               historical news for any date range (Jan 2026 →)
# ============================================================

import feedparser
import json
import re
import time
from google import genai
from google.genai import types, errors
from datetime import datetime
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup

from config import RSS_FEEDS, GEMINI_API_KEY, GEMINI_MODEL
from database import save_article

client = genai.Client(api_key=GEMINI_API_KEY)


# ─────────────────────────────────────────────────────────
#  A) RSS Fetcher  (daily / recent)
# ─────────────────────────────────────────────────────────

def _clean(html):
    return " ".join(BeautifulSoup(html or "", "html.parser").get_text().split())[:1500]


def _parse_date(entry):
    for f in ("published", "updated"):
        try:
            return parsedate_to_datetime(entry.get(f, "")).strftime("%Y-%m-%d")
        except Exception:
            pass
    return datetime.utcnow().strftime("%Y-%m-%d")


def fetch_rss(since: str = None) -> int:
    """Pull articles from all RSS feeds. `since` = YYYY-MM-DD filter."""
    since_dt = datetime.strptime(since, "%Y-%m-%d").date() if since else None
    saved = 0
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                link  = e.get("link", "").strip()
                title = e.get("title", "").strip()
                if not link or not title:
                    continue
                pub = _parse_date(e)
                if since_dt and datetime.strptime(pub, "%Y-%m-%d").date() < since_dt:
                    continue
                summary = _clean(e.get("summary") or e.get("description") or "")
                source  = feed.feed.get("title", url)
                save_article(link, title, summary, source, pub)
                saved += 1
        except Exception as ex:
            print(f"[RSS] Error {url}: {ex}")
    print(f"[RSS] Saved {saved} articles.")
    return saved


# ─────────────────────────────────────────────────────────
#  B) Historical Search Fetcher  (Jan 2026 → Apr 2026)
#     Uses Claude + web_search tool to find news by week
# ─────────────────────────────────────────────────────────

SEARCH_PROMPT = """
You are a current affairs researcher for UPSC Civil Services preparation.
Search the web and compile a list of the TOP 15 most important current affairs
news items from India and the world for the period: {start} to {end}.

Focus on:
- Government policies and schemes (Central/State)
- Economy, RBI, Budget, Trade
- Science & Technology (ISRO, AI, Health, Environment)
- International relations (India's bilateral/multilateral)
- Awards, appointments, summits, reports/indices
- Environment, biodiversity, climate

For EACH news item, return a JSON object with:
  "title": short headline
  "summary": 3-5 sentence factual description (NO opinions)
  "date": best estimate YYYY-MM-DD within the range
  "category": one of [Economy, Polity, Science, Environment, International, Misc]

Return ONLY a valid JSON array of 15 objects. No markdown, no preamble.
"""


def _extract_json_array(text: str) -> str:
    """Find the JSON array inside Claude's response (handles prose/markdown wrappers)."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:])
    start = text.find("[")
    end   = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def _is_rate_limit(exc: Exception) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    return code == 429 or "RESOURCE_EXHAUSTED" in str(exc).upper() or "429" in str(exc)


def fetch_historical(week_start: str, week_end: str, max_retries: int = 4) -> list:
    """
    Call Gemini with Google Search grounding to find news for a specific week.
    Retries with exponential backoff on rate-limit (429) errors.
    Returns list of article dicts saved to DB.
    """
    print(f"[Search] Fetching news for week {week_start} → {week_end} …")
    prompt = SEARCH_PROMPT.format(start=week_start, end=week_end)

    config = types.GenerateContentConfig(
        max_output_tokens=8000,
        temperature=0.3,
        tools=[types.Tool(google_search=types.GoogleSearch())],
    )

    backoff = 30
    for attempt in range(1, max_retries + 1):
        text = ""
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=config,
            )
            text = (resp.text or "").strip()

            payload = _extract_json_array(text)
            articles = json.loads(payload)
            print(f"[Search] Got {len(articles)} articles for {week_start}–{week_end}.")

            saved = []
            for a in articles:
                title   = a.get("title", "").strip()
                summary = a.get("summary", "").strip()
                date    = a.get("date", week_start)
                cat     = a.get("category", "Misc")
                url     = f"search://{week_start}/{title[:60].replace(' ', '-')}"
                save_article(url, title, summary, f"Web Search ({cat})", date)
                saved.append({"title": title, "summary": summary, "pub_date": date, "category": cat})

            return saved

        except errors.APIError as e:
            if _is_rate_limit(e):
                if attempt == max_retries:
                    print(f"[Search] Rate-limit hit and out of retries: {e}")
                    return []
                print(f"[Search] Rate-limit (attempt {attempt}/{max_retries}). Sleeping {backoff}s …")
                time.sleep(backoff)
                backoff = min(backoff * 2, 240)
            else:
                print(f"[Search] API error: {e}")
                return []

        except json.JSONDecodeError:
            print(f"[Search] JSON parse failed. Raw start: {text[:300]!r}")
            return []

        except Exception as e:
            print(f"[Search] Unexpected error: {e}")
            return []

    return []
