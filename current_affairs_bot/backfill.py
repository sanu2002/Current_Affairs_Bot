# ============================================================
#  backfill.py — Agent 4: Historical Backfill
#
#  Strategy:
#   • Splits Jan 2026 → today into WEEKLY batches
#   • For each week: calls Claude with web_search to get news
#   • Generates QUESTIONS_PER_DAY questions for ONE representative
#     date per week (Monday), then sends that batch to Telegram
#
#  Run ONCE:  python backfill.py
#  Dry run:   python backfill.py --no-send
#  Custom:    python backfill.py --start 2026-02-01 --end 2026-03-31
# ============================================================

import time, argparse
from datetime import datetime, timedelta

from config import BACKFILL_START, QUESTIONS_PER_DAY
from database import init_db, get_questions
from news_fetcher import fetch_historical
from question_generator import generate_from_raw_articles
from telegram_sender import send_daily


# ─────────────────────────────────────────────────────────
#  Week iterator
# ─────────────────────────────────────────────────────────

def weekly_ranges(start: str, end: str):
    """Yield (week_start, week_end) pairs from start to end."""
    cur  = datetime.strptime(start, "%Y-%m-%d")
    stop = datetime.strptime(end,   "%Y-%m-%d")
    while cur <= stop:
        week_end = min(cur + timedelta(days=6), stop)
        yield cur.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")
        cur += timedelta(days=7)


# ─────────────────────────────────────────────────────────
#  Main backfill
# ─────────────────────────────────────────────────────────

def run_backfill(
    start: str = BACKFILL_START,
    end:   str = None,
    send:  bool = True,
    pause: int  = 75,      # seconds between weeks (Anthropic 10k tpm tier)
):
    init_db()
    if end is None:
        end = datetime.utcnow().strftime("%Y-%m-%d")

    weeks = list(weekly_ranges(start, end))
    print(f"\n[Backfill] {len(weeks)} weeks from {start} → {end}")
    print(f"[Backfill] Send to Telegram: {send}\n")

    for idx, (wk_start, wk_end) in enumerate(weeks, 1):
        # Use Monday (wk_start) as the representative date for this batch
        date_label = wk_start
        print(f"\n── Week {idx}/{len(weeks)}:  {wk_start} → {wk_end}  ──")

        # Skip if already generated
        existing = get_questions(date_label)
        if len(existing) >= QUESTIONS_PER_DAY:
            print(f"  Already have {len(existing)} questions. Skipping generation.")
        else:
            # Step 1: fetch news for this week via Claude web_search
            articles = fetch_historical(wk_start, wk_end)
            if not articles:
                print(f"  [!] No articles found for week {wk_start}. Skipping.")
                continue

            # Step 2: generate questions
            count = generate_from_raw_articles(date_label, articles, n=QUESTIONS_PER_DAY)
            if count == 0:
                print(f"  [!] No questions generated. Skipping send.")
                continue
            print(f"  Generated {count} questions.")

        # Step 3: send to Telegram
        if send:
            ok = send_daily(date_label, force=False)
            if ok:
                print(f"  ✓ Sent to Telegram ({date_label}).")
            time.sleep(pause)

    print("\n[Backfill] ✅ Done.")


# ─────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backfill current affairs Jan 2026 → today")
    ap.add_argument("--start",   default=BACKFILL_START, help="Start date YYYY-MM-DD")
    ap.add_argument("--end",     default=None,           help="End date YYYY-MM-DD (default: today)")
    ap.add_argument("--no-send", action="store_true",    help="Generate but don't send to Telegram")
    ap.add_argument("--pause",   type=int, default=75,   help="Seconds between weeks (default: 75)")
    args = ap.parse_args()

    run_backfill(
        start = args.start,
        end   = args.end,
        send  = not args.no_send,
        pause = args.pause,
    )
