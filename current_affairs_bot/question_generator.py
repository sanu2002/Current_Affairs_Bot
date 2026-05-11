# ============================================================
#  question_generator.py — Agent 2: MCQ Generator
#
#  Generates questions in the EXACT format as the
#  Feb–March Current Affairs PDF sample.
# ============================================================

import json, time, anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, QUESTIONS_PER_DAY
from database import get_unused_articles, mark_used, save_questions, get_questions

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─────────────────────────────────────────────────────────
#  System prompt — mirrors PDF format EXACTLY
# ─────────────────────────────────────────────────────────
SYSTEM = """
You are an expert question-setter for the UPSC Civil Services Preliminary Examination,
specialising in Current Affairs. Generate MCQs that are IDENTICAL in style to official
UPSC prelims papers.

═══════════════════════════════════════════════════════════════
QUESTION TEMPLATES  (use all three, mixed)
═══════════════════════════════════════════════════════════════

── TEMPLATE 1 ── Statement-based  (most common)
With reference to [TOPIC], consider the following statements:
1. [Statement — may be correct or incorrect]
2. [Statement — may be correct or incorrect]
3. [Optional third statement]
Which of the statements given above is/are correct?
A. 1 only
B. 2 and 3 only
C. 1 and 3 only
D. 1, 2 and 3

── TEMPLATE 2 ── Pair-matching
With reference to [TOPIC], consider the following pairs:
        [Column 1 header]        [Column 2 header]
1.  [Item A]                 [Match A]
2.  [Item B]                 [Match B]
3.  [Item C]                 [Match C]
Which of the pairs given above is/are correctly matched?
A. 1 and 2 only
B. 2 only
C. 1 and 3 only
D. 1, 2 and 3

── TEMPLATE 3 ── Direct / Best-explains
Which of the following best describes / explains [TOPIC]?
  OR
The term '[TERM]', recently seen in the news, refers to which of the following?
  OR
How many of the following statements about [TOPIC] are correct?
1. [Statement]
2. [Statement]
A. Only one
B. Only two
C. All three
D. None

═══════════════════════════════════════════════════════════════
EXPLANATION FORMAT  (mirrors PDF solutions section EXACTLY)
═══════════════════════════════════════════════════════════════

Context : [One sentence — the news event that prompted this question]
• [Statement 1 analysis — say "is correct" or "is not correct" + reason]
• [Statement 2 analysis]
• [Optional statement 3 analysis]
Hence, option [X] is correct.

═══════════════════════════════════════════════════════════════
OUTPUT  — valid JSON array ONLY, no markdown fences, no preamble
═══════════════════════════════════════════════════════════════

Each element:
{
  "template":     "1" | "2" | "3",
  "topic":        "<concise topic label>",
  "category":     "Economy" | "Polity" | "Science" | "Environment" | "International" | "Misc",
  "question":     "<full question text — include numbered statements inside>",
  "options": {
    "A": "<option text>",
    "B": "<option text>",
    "C": "<option text>",
    "D": "<option text>"
  },
  "correct":      "A" | "B" | "C" | "D",
  "explanation":  "<Context sentence.\\n• bullet 1\\n• bullet 2\\nHence, option X is correct.>"
}

STRICT RULES:
- Every question must be traceable to a provided article.
- Distractors must be factually plausible but clearly wrong on careful reading.
- Avoid trivial questions. Aim for moderate-to-hard UPSC difficulty.
- Do NOT repeat topics across questions.
- Options for Template 1 & 2 must always follow UPSC combo patterns:
  e.g.  "1 only",  "2 and 3 only",  "1 and 2 only",  "1, 2 and 3"
"""


def _user_prompt(articles: list, n: int) -> str:
    block = ""
    for i, a in enumerate(articles, 1):
        block += (
            f"\n[Article {i}]\n"
            f"Title   : {a['title']}\n"
            f"Date    : {a['pub_date']}\n"
            f"Summary : {a['summary']}\n"
        )
    return (
        f"Based on the articles below, generate exactly {n} UPSC Prelims Current Affairs MCQs.\n"
        f"Use a mix of all three templates. Output ONLY the JSON array.\n\n"
        f"{block}"
    )


def _call_claude(articles: list, n: int, max_retries: int = 4) -> list:
    prompt = _user_prompt(articles, n)
    backoff = 30
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=16000,
                system=SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:])
                if raw.endswith("```"):
                    raw = raw[:-3]
            return json.loads(raw.strip())
        except anthropic.RateLimitError as e:
            if attempt == max_retries:
                print(f"[Gen] Rate-limit and out of retries: {e}")
                return []
            print(f"[Gen] Rate-limit (attempt {attempt}/{max_retries}). Sleeping {backoff}s …")
            time.sleep(backoff)
            backoff = min(backoff * 2, 240)
        except json.JSONDecodeError as e:
            print(f"[Gen] JSON error: {e}")
            return []
        except Exception as e:
            print(f"[Gen] API error: {e}")
            return []
    return []


def generate_for_date(date_str: str, articles: list = None, n: int = None) -> int:
    """
    Generate `n` questions for `date_str`.
    If articles is None, pulls from DB unused pool.
    Returns count of questions saved.
    """
    n = n or QUESTIONS_PER_DAY

    # Check if already generated
    existing = get_questions(date_str)
    if len(existing) >= n:
        print(f"[Gen] Already have {len(existing)} questions for {date_str}.")
        return len(existing)

    if articles is None:
        articles = get_unused_articles(limit=12)

    if not articles:
        print(f"[Gen] No articles available for {date_str}.")
        return 0

    print(f"[Gen] Generating {n} questions for {date_str} from {len(articles)} articles…")
    qs = _call_claude(articles[:10], n)   # max 10 articles per call

    if not qs:
        return 0

    save_questions(date_str, qs[:n])
    mark_used([a["id"] for a in articles if "id" in a])
    print(f"[Gen] Saved {len(qs[:n])} questions for {date_str}.")
    return len(qs[:n])


def generate_from_raw_articles(date_str: str, raw_articles: list, n: int = None) -> int:
    """
    Generate questions directly from a list of raw dicts
    (title, summary, pub_date) — used by the backfill agent.
    """
    n = n or QUESTIONS_PER_DAY
    existing = get_questions(date_str)
    if len(existing) >= n:
        print(f"[Gen] Already have {len(existing)} questions for {date_str}. Skipping.")
        return len(existing)

    print(f"[Gen] Generating {n} questions for {date_str} from {len(raw_articles)} raw articles…")
    qs = _call_claude(raw_articles, n)
    if not qs:
        return 0
    save_questions(date_str, qs[:n])
    print(f"[Gen] Saved {len(qs[:n])} questions for {date_str}.")
    return len(qs[:n])
