# 🗞️ Current Affairs UPSC MCQ Bot

Generates **UPSC Prelims-style** Current Affairs MCQs from **January 2026 to today**
and delivers them to Telegram daily — in the **exact same format** as the
Feb–March Current Affairs PDF.

---

## 📐 Telegram Output Format  (matches PDF exactly)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━
🗞️ CURRENT AFFAIRS — 15 JANUARY 2026
📋 15 Questions | UPSC Prelims Style
━━━━━━━━━━━━━━━━━━━━━━━━━━

Q.1  🏛️  `Fiscal Health Index`
─────────────────────────────
With reference to the Fiscal Health Index (FHI), consider the
following statements:
1. The Fiscal Health Index is released by NITI Aayog to assess
   the fiscal performance of Indian states.
2. The index evaluates states on revenue mobilisation, quality of
   expenditure, fiscal prudence, and debt sustainability.

Which of the statements given above is/are correct?

  A. 1 only
  B. 2 only
  C. Both 1 and 2
  D. Neither 1 nor 2

Correct: +2 · Incorrect: -0.67
══════════════════════
✅ Correct Answer : C

Context : NITI Aayog released the Fiscal Health Index 2025.
• Statement 1 is correct: FHI is published by NITI Aayog, not WHO.
• Statement 2 is correct: The index covers revenue mobilisation,
  expenditure quality, fiscal prudence and debt sustainability.
Hence, option C is correct.
```

---

## 🏗️ Architecture

```
  ┌─────────────────┐     ┌──────────────────┐     ┌────────────────┐
  │  Agent 1        │     │  Agent 2         │     │  Agent 3       │
  │  News Fetcher   │────▶│  MCQ Generator   │────▶│  TG Publisher  │
  │                 │     │  (Claude API)    │     │  (Bot API)     │
  │ • RSS (daily)   │     │  3 templates     │     │  PDF format    │
  │ • Web search    │     │  matching PDF    │     │                │
  │   (historical)  │     │                  │     │                │
  └─────────────────┘     └──────────────────┘     └────────────────┘
          │                        │                        │
          └────────────────────────┴────────────────────────┘
                                   │
                            ┌──────────────┐
                            │  SQLite DB   │
                            └──────────────┘
                                   │
                       ┌───────────────────────┐
                       │  Agent 4 — Backfill   │
                       │  Jan 2026 → today     │
                       │  (run ONCE)           │
                       └───────────────────────┘
```

### Question Templates (exact PDF match)
| Template | Style | Example trigger |
|----------|-------|-----------------|
| 1 | Statement-based | "consider the following statements…" |
| 2 | Pair-matching | "consider the following pairs…" |
| 3 | Direct MCQ | "Which of the following best describes…" |

**Marking:** Correct +2 · Incorrect -0.67 (UPSC standard)

---

## ⚙️ Setup

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Get API keys

**Anthropic (Claude)**
- Sign up at platform.anthropic.com
- Create an API key

**Telegram Bot**
1. Open Telegram → message `@BotFather`
2. `/newbot` → follow steps → copy **Bot Token**
3. Add bot to your channel/group as **Admin**
4. Get Chat ID:
   - Channel: `@channelname`
   - Group: visit `api.telegram.org/bot<TOKEN>/getUpdates`, find `"chat":{"id":-100...}`

### 3. Configure
```bash
cp .env.example .env
# Edit .env and fill in your 3 keys
```

### 4. Test connection
```bash
python main.py test
```

---

## 🚀 Usage

### Step 1 — Backfill (run ONCE, Jan 2026 → today)
```bash
# Full backfill with Telegram send
python backfill.py

# Generate only, no send yet
python backfill.py --no-send

# Specific range
python backfill.py --start 2026-01-01 --end 2026-04-30
```

This processes **weekly batches** — for each week:
- Searches web for top 15 India current affairs (via Claude)
- Generates 15 UPSC-style MCQs
- Sends to Telegram

### Step 2 — Daily automation
```bash
python main.py run        # Starts scheduler, sends at 08:00 IST daily
```

### Manual commands
```bash
python main.py fetch      # Pull RSS articles
python main.py generate   # Generate today's questions
python main.py send       # Send today's questions
python main.py once --date 2026-03-15 --force   # Specific date
```

---

## 📁 File Structure
```
current_affairs_bot/
├── main.py               # Orchestrator + scheduler
├── config.py             # All settings
├── database.py           # SQLite (articles + questions + log)
├── news_fetcher.py       # Agent 1: RSS + Claude web search
├── question_generator.py # Agent 2: Claude MCQ generator
├── telegram_sender.py    # Agent 3: PDF-format Telegram publisher
├── backfill.py           # Agent 4: Jan 2026 → today
├── requirements.txt
├── .env.example
└── bot_data.db           # Auto-created
```

---

## ☁️ Deployment

### Railway / Render (easiest, free tier)
1. Push to GitHub
2. Connect to railway.app or render.com
3. Add env vars in dashboard
4. Start command: `python main.py run`

### VPS (systemd)
```bash
# /etc/systemd/system/upsc-bot.service
[Unit]
Description=UPSC Current Affairs Bot
[Service]
WorkingDirectory=/home/ubuntu/current_affairs_bot
ExecStart=python3 main.py run
EnvironmentFile=/home/ubuntu/current_affairs_bot/.env
Restart=always
[Install]
WantedBy=multi-user.target
```

---

## 💰 Cost
| Item | Cost |
|------|------|
| Claude API (15 Q/day) | ~$1–2/month |
| Telegram Bot | Free |
| RSS feeds | Free |
| Web search (backfill) | Included in Claude API |
