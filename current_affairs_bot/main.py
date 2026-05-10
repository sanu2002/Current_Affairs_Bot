# ============================================================
#  main.py — Orchestrator + Daily Scheduler
# ============================================================

import schedule, time, argparse
from datetime import datetime

from config import SEND_TIME, QUESTIONS_PER_DAY
from database import init_db
from news_fetcher import fetch_rss
from question_generator import generate_for_date
from telegram_sender import send_daily, test_bot


def daily_pipeline():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    print(f"\n{'='*50}\n[Pipeline] {today}\n{'='*50}")

    print("\n── 1/3  Fetch RSS ──")
    fetch_rss(since=today)

    print("\n── 2/3  Generate questions ──")
    n = generate_for_date(today, n=QUESTIONS_PER_DAY)
    if n == 0:
        print("[Pipeline] No questions — aborting.")
        return

    print("\n── 3/3  Send to Telegram ──")
    send_daily(today)
    print("\n[Pipeline] ✓ Done.")


def start_scheduler():
    print(f"[Scheduler] Running daily at {SEND_TIME} IST. Ctrl+C to stop.")
    schedule.every().day.at(SEND_TIME).do(daily_pipeline)
    daily_pipeline()         # run once immediately on start
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("run",      help="Start daily scheduler")
    sub.add_parser("test",     help="Test Telegram connection")
    sub.add_parser("fetch",    help="Fetch RSS articles now")
    sub.add_parser("generate", help="Generate today's questions")
    sub.add_parser("send",     help="Send today's questions")
    p = sub.add_parser("once", help="Full pipeline for a date")
    p.add_argument("--date",  default=None)
    p.add_argument("--force", action="store_true")
    args = ap.parse_args()

    init_db()

    if   args.cmd == "run":      start_scheduler()
    elif args.cmd == "test":     test_bot()
    elif args.cmd == "fetch":    fetch_rss()
    elif args.cmd == "generate": generate_for_date(datetime.utcnow().strftime("%Y-%m-%d"))
    elif args.cmd == "send":     send_daily(datetime.utcnow().strftime("%Y-%m-%d"))
    elif args.cmd == "once":
        d = args.date or datetime.utcnow().strftime("%Y-%m-%d")
        fetch_rss(since=d)
        generate_for_date(d)
        send_daily(d, force=args.force)
    else:
        ap.print_help()
