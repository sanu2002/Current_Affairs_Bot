# ============================================================
#  database.py
# ============================================================
import sqlite3, json
from datetime import datetime
from config import DB_PATH


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            url        TEXT UNIQUE,
            title      TEXT,
            summary    TEXT,
            source     TEXT,
            pub_date   TEXT,
            used       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS questions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date_for    TEXT,
            q_number    INTEGER,
            q_json      TEXT,
            sent        INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS send_log (
            date_for TEXT PRIMARY KEY,
            sent_at  TEXT
        );
        """)
    print("[DB] Ready.")


# ── Articles ──────────────────────────────────────────────
def save_article(url, title, summary, source, pub_date):
    try:
        with _conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO articles (url,title,summary,source,pub_date) VALUES (?,?,?,?,?)",
                (url, title, summary, source, pub_date)
            )
            c.commit()
    except Exception as e:
        print(f"[DB] save_article error: {e}")


def get_unused_articles(limit=20):
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM articles WHERE used=0 ORDER BY pub_date DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def mark_used(article_ids):
    if not article_ids:
        return
    ph = ",".join("?" * len(article_ids))
    with _conn() as c:
        c.execute(f"UPDATE articles SET used=1 WHERE id IN ({ph})", article_ids)
        c.commit()


# ── Questions ─────────────────────────────────────────────
def save_questions(date_for, questions: list):
    with _conn() as c:
        for i, q in enumerate(questions, 1):
            c.execute(
                "INSERT INTO questions (date_for, q_number, q_json) VALUES (?,?,?)",
                (date_for, i, json.dumps(q))
            )
        c.commit()


def get_questions(date_for) -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM questions WHERE date_for=? ORDER BY q_number", (date_for,)
        ).fetchall()
    return [dict(r) for r in rows]


def already_sent(date_for) -> bool:
    with _conn() as c:
        return c.execute(
            "SELECT 1 FROM send_log WHERE date_for=?", (date_for,)
        ).fetchone() is not None


def log_sent(date_for):
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO send_log (date_for, sent_at) VALUES (?,?)",
            (date_for, datetime.utcnow().isoformat())
        )
        c.commit()
