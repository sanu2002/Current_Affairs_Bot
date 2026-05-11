# ============================================================
#  telegram_sender.py — Agent 3: Telegram Publisher
#
#  Output format mirrors the Feb–March PDF exactly:
#    • Question section (numbered, with statements/options)
#    • Correct: +2 · Incorrect: -0.67  per question
#    • Answer section (Correct Answer : X)
#    • Solutions / Explanation section (Context + bullets)
# ============================================================

import json, time, requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from database import get_questions, already_sent, log_sent

API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ─────────────────────────────────────────────────────────
#  Emoji map
# ─────────────────────────────────────────────────────────
CAT_EMOJI = {
    "Economy":       "📈",
    "Polity":        "🏛️",
    "Science":       "🔬",
    "Environment":   "🌿",
    "International": "🌐",
    "Misc":          "📌",
}

# ─────────────────────────────────────────────────────────
#  Telegram MarkdownV2 escaper
# ─────────────────────────────────────────────────────────
_SPECIAL = r"\_*[]()~`>#+-=|{}.!"

def esc(s: str) -> str:
    return "".join(f"\\{c}" if c in _SPECIAL else c for c in str(s))


# ─────────────────────────────────────────────────────────
#  Message builders  (replicating the PDF layout)
# ─────────────────────────────────────────────────────────

def _header(date_str: str, total: int, kind: str = "daily", week_end: str = None) -> str:
    """
    kind="daily"  -> "DAILY CURRENT AFFAIRS — 11 MAY 2026"
    kind="weekly" -> "WEEKLY CURRENT AFFAIRS — 01 JAN to 07 JAN 2026"
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if kind == "weekly" and week_end:
        end_dt = datetime.strptime(week_end, "%Y-%m-%d")
        label  = f"{dt.strftime('%d %b').upper()} TO {end_dt.strftime('%d %b %Y').upper()}"
        title  = "WEEKLY CURRENT AFFAIRS"
    else:
        label  = dt.strftime("%d %B %Y").upper()
        title  = "DAILY CURRENT AFFAIRS"
    return (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🗞️ *{esc(title)} — {esc(label)}*\n"
        f"📋 *{total} Questions \\| UPSC Prelims Style*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def _question_block(q_json: dict, serial: int) -> str:
    """
    Renders one question in PDF style:

    Q.1  [Category emoji]  topic
    ─────────────────────────────
    With reference to … consider the following statements:
    1. Statement one.
    2. Statement two.
    Which of the statements given above is/are correct?

    A. 1 only
    B. 2 only
    C. Both 1 and 2
    D. Neither 1 nor 2

    Correct: +2 · Incorrect: -0.67
    ══════════════════════
    Correct Answer : C

    Context : ...
    • Statement 1 is correct: ...
    • Statement 2 is not correct: ...
    Hence, option C is correct.
    """
    q       = q_json.get("question", "")
    opts    = q_json.get("options", {})
    correct = q_json.get("correct", "?")
    expl    = q_json.get("explanation", "")
    cat     = q_json.get("category", "Misc")
    topic   = q_json.get("topic", "")
    emoji   = CAT_EMOJI.get(cat, "📌")

    # ── Option lines ──
    opt_lines = "\n".join(
        f"  *{letter}\\.* {esc(text)}"
        for letter, text in sorted(opts.items())
    )

    # ── Explanation — preserve bullet points ──
    expl_lines = []
    for line in expl.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("•"):
            expl_lines.append("  " + esc(line))
        elif line.lower().startswith("context"):
            expl_lines.append(f"*{esc(line)}*")
        elif line.lower().startswith("hence"):
            expl_lines.append(f"_{esc(line)}_")
        else:
            expl_lines.append(esc(line))
    expl_text = "\n".join(expl_lines)

    msg = (
        f"*Q\\.{serial}*  {emoji}  `{esc(topic)}`\n"
        f"─────────────────────────────\n"
        f"{esc(q)}\n\n"
        f"{opt_lines}\n\n"
        f"Correct: \\+2 · Incorrect: \\-0\\.67\n"
        f"══════════════════════\n"
        f"✅ *Correct Answer : {esc(correct)}*\n\n"
        f"{expl_text}"
    )
    return msg


def _footer() -> str:
    return (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 *Daily Current Affairs* \\| UPSC Prelims\n"
        "_Study smart\\. Revise daily\\. Crack UPSC\\._"
    )


# ─────────────────────────────────────────────────────────
#  Sender
# ─────────────────────────────────────────────────────────

def _send(text: str) -> bool:
    for attempt in range(3):
        try:
            r = requests.post(
                f"{API}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID,
                      "text": text,
                      "parse_mode": "MarkdownV2"},
                timeout=20,
            ).json()
            if r.get("ok"):
                return True
            print(f"  [TG] Error: {r.get('description')} (attempt {attempt+1})")
        except Exception as e:
            print(f"  [TG] Request error: {e} (attempt {attempt+1})")
        time.sleep(3)
    return False


def send_daily(date_str: str, force: bool = False,
               kind: str = "daily", week_end: str = None) -> bool:
    if not force and already_sent(date_str):
        print(f"[Sender] Already sent for {date_str}.")
        return False

    rows = get_questions(date_str)
    if not rows:
        print(f"[Sender] No questions for {date_str}.")
        return False

    print(f"[Sender] Sending {len(rows)} questions for {date_str} …")

    # ── Header ──
    _send(_header(date_str, len(rows), kind=kind, week_end=week_end))
    time.sleep(1.5)

    # ── One message per question ──
    ok_count = 0
    for i, row in enumerate(rows, 1):
        q = json.loads(row["q_json"])
        if _send(_question_block(q, i)):
            ok_count += 1
        else:
            print(f"  [Sender] Failed Q{i}")
        time.sleep(2)   # ~20 msgs/min limit

    # ── Footer ──
    _send(_footer())

    if ok_count:
        log_sent(date_str)
        print(f"[Sender] ✓ {ok_count}/{len(rows)} sent for {date_str}.")
        return True
    return False


# ─────────────────────────────────────────────────────────
#  Utilities
# ─────────────────────────────────────────────────────────

def test_bot() -> bool:
    r = requests.get(f"{API}/getMe", timeout=10).json()
    if r.get("ok"):
        print(f"[TG] ✓ Bot: @{r['result']['username']}")
        return True
    print(f"[TG] ✗ {r}")
    return False


def send_text(text: str) -> bool:
    """Send a plain text message (no markdown)."""
    r = requests.post(
        f"{API}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=15,
    ).json()
    return r.get("ok", False)
