# ============================================================
#  backfill.py — Historical Backfill (state-tracked, daily-friendly)
#
#  Walks Jan 2026 → today in weekly batches. Each invocation processes
#  up to --max-weeks weeks (default 1) and updates backfill_state.json
#  so the next run picks up where this one left off. This keeps each
#  GitHub Actions run small and well under the Anthropic 10k tpm tier.
#
#  Run locally:        python backfill.py
#  Dry run:            python backfill.py --no-send
#  Specific window:    python backfill.py --start 2026-02-01 --end 2026-03-31
#  Multiple per run:   python backfill.py --max-weeks 3
#  Reset progress:     delete backfill_state.json
# ============================================================

import json, os, time, argparse
from datetime import datetime, timedelta

from config import BACKFILL_START, QUESTIONS_PER_DAY
from database import init_db, get_questions
from news_fetcher import fetch_historical
from question_generator import generate_from_raw_articles
from telegram_sender import send_daily


STATE_PATH = "backfill_state.json"


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[State] Read error: {e}. Starting fresh.")
    return {}


def save_state(state: dict):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def weekly_ranges(start: str, end: str):
    cur  = datetime.strptime(start, "%Y-%m-%d")
    stop = datetime.strptime(end,   "%Y-%m-%d")
    while cur <= stop:
        week_end = min(cur + timedelta(days=6), stop)
        yield cur.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")
        cur += timedelta(days=7)


def run_backfill(
    start: str = BACKFILL_START,
    end:   str = None,
    send:  bool = True,
    pause: int  = 75,
    max_weeks: int = 1,
):
    init_db()
    if end is None:
        end = datetime.utcnow().strftime("%Y-%m-%d")

    state = load_state()
    last_done = state.get("completed_through")
    if last_done:
        cursor_dt = datetime.strptime(last_done, "%Y-%m-%d") + timedelta(days=1)
        cursor    = cursor_dt.strftime("%Y-%m-%d")
        if cursor > end:
            print(f"[Backfill] Caught up. last completed week ends {last_done}.")
            return
        effective_start = cursor
        print(f"[Backfill] Resuming after {last_done} -> from {effective_start}")
    else:
        effective_start = start
        print(f"[Backfill] No prior state. Starting from {effective_start}")

    weeks = list(weekly_ranges(effective_start, end))
    if not weeks:
        print("[Backfill] Nothing to process.")
        return

    print(f"[Backfill] {len(weeks)} week(s) remaining. Processing up to {max_weeks} this run.")
    print(f"[Backfill] Send to Telegram: {send}\n")

    processed = 0
    for idx, (wk_start, wk_end) in enumerate(weeks, 1):
        if processed >= max_weeks:
            print(f"[Backfill] Reached max-weeks={max_weeks}. Stopping for this run.")
            break

        date_label = wk_start
        print(f"\n-- Week {idx}/{len(weeks)}: {wk_start} -> {wk_end} --")

        existing = get_questions(date_label)
        if len(existing) >= QUESTIONS_PER_DAY:
            print(f"  Already have {len(existing)} questions. Skipping generation.")
        else:
            articles = fetch_historical(wk_start, wk_end)
            if not articles:
                print(f"  [!] No articles found for week {wk_start}. Stopping run.")
                break

            count = generate_from_raw_articles(date_label, articles, n=QUESTIONS_PER_DAY)
            if count == 0:
                print(f"  [!] No questions generated. Stopping run.")
                break
            print(f"  Generated {count} questions.")

        if send:
            ok = send_daily(date_label, force=False, kind="weekly", week_end=wk_end)
            if ok:
                print(f"  Sent to Telegram (week {wk_start} -> {wk_end}).")

        state["completed_through"] = wk_end
        save_state(state)
        processed += 1

        if processed < max_weeks and idx < len(weeks):
            time.sleep(pause)

    print(f"\n[Backfill] Done. Processed {processed} week(s) this run. Last completed: {state.get('completed_through')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backfill current affairs Jan 2026 -> today")
    ap.add_argument("--start",     default=BACKFILL_START, help="Start date YYYY-MM-DD (ignored if state file exists)")
    ap.add_argument("--end",       default=None,           help="End date YYYY-MM-DD (default: today)")
    ap.add_argument("--no-send",   action="store_true",    help="Generate but don't send to Telegram")
    ap.add_argument("--pause",     type=int, default=75,   help="Seconds between weeks (default: 75)")
    ap.add_argument("--max-weeks", type=int, default=1,    help="Max weeks to process per run (default: 1)")
    args = ap.parse_args()

    run_backfill(
        start     = args.start,
        end       = args.end,
        send      = not args.no_send,
        pause     = args.pause,
        max_weeks = args.max_weeks,
    )
