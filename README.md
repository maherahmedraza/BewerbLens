# BewerbLens

> **BewerbLens** — Your intelligent lens on the job application process. An end-to-end, AI-powered job application tracker that automatically ingests, classifies, and monitors your job application emails — then surfaces everything on a beautiful real-time dashboard.

---

## Overview

BewerbLens solves a universal problem for job seekers: **tracking applications scattered across email inboxes, spreadsheets, and job portals**. It replaces manual tracking with an automated pipeline that:

1. **Fetches** emails from Gmail continuously
2. **Classifies** them with Google Gemini AI (Applied, Rejected, Interview, Offer, etc.)
3. **Stores** everything in Supabase with zero-duplicate guarantees
4. **Notifies** you via Telegram when status changes occur
5. **Visualizes** your entire job search on a Next.js dashboard with analytics

---

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   Gmail API │────>│  Python Pipeline │────>│   Supabase   │────>│  Telegram   │────>│  Next.js     │
│  (Ingest)   │     │  (AI Classify)   │     │  (Postgres)  │     │  (Notify)   │     │  Dashboard   │
└─────────────┘     └──────────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
```

### Components

| Component | Tech Stack | Purpose |
|---|---|---|
| **BewerbLens Tracker** | Python 3.11+, Pydantic, Gemini AI | Automated email ingestion & classification |
| **Dashboard** | Next.js 16, React 19, Recharts, Supabase SSR | Real-time application tracking UI |
| **n8n Workflow** | n8n (Docker) | Original visual workflow (legacy reference) |
| **Database** | Supabase (PostgreSQL) | Persistent storage with deduplication |
| **Infrastructure** | Docker Compose | One-command local deployment |

---

## Features

### BewerbLens Tracker
- **Incremental checkpointing** — only processes new emails since last run
- **Gemini AI classification** — detects Application, Rejection, Interview, Offer, and Positive Response
- **Confidence scoring** — configurable threshold to filter uncertain classifications
- **Native deduplication** — PostgreSQL `UNIQUE` constraints on `thread_id`
- **Telegram notifications** — instant alerts for new applications and status changes
- **GitHub Actions ready** — runs automatically on a cron schedule (free tier)
- **Structured logging** — `loguru` with rotation, replacing n8n's debugging nightmare

### Dashboard
- **Overview page** — stats cards with total applications, response rate, and success rate
- **Applications table** — searchable, filterable list of all tracked applications
- **Analytics page** — charts for platform breakdown, status distribution, and trends
- **Dark/Light mode** — theme toggle with persistent preference
- **Authentication** — Supabase Auth for secure access
- **Settings page** — configuration management

---

## Project Structure

```
BewerbLens/
├── apps/                          # Deployable Applications
│   ├── tracker/                   # Python AI pipeline
│   │   ├── tracker.py             # Main pipeline orchestrator
│   │   ├── config.py              # Pydantic settings
│   │   ├── models.py              # Data models & enums
│   │   ├── gmail_service.py       # Gmail API connection
│   │   ├── pyproject.toml         # Python dependencies
│   │   └── ...
│   │
│   └── dashboard/                 # Next.js web application
│       ├── src/
│       │   ├── app/               # Next.js App Router pages
│       │   ├── components/        # Reusable UI components
│       │   └── lib/               # Utilities & Supabase client
│       └── package.json
│
├── scripts/                       # Infrastructure & Configurations
│   └── n8n/                       
│       ├── workflows/             # Legacy & active n8n workflows
│       └── backups/               # Automated workflow backups
│
├── .github/                       # Security & CI Configurations
│   └── dependabot.yml             # Automatic dependency updates
│
├── .env.example                   # Universal environment template
├── .gitattributes                 # Cross-platform normalizing
├── .pre-commit-config.yaml        # Code formatting enforcement
├── docker-compose.yml             # Local Docker infrastructure
└── README.md                      # This file
```

---

## Quick Start

### Prerequisites

- **Python 3.11+** (for BewerbLens Tracker)
- **Node.js 18+** (for Dashboard)
- **Docker & Docker Compose** (for n8n)
- **Supabase account** (free tier works)
- **Google Cloud project** with Gmail API enabled
- **Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Configure the Environment
We use a root-level template for all secrets.
```bash
cp .env.example .env
# Edit .env with your credentials (Supabase, Gemini, Postgres)
```

### 2. Set Up Database (Supabase)
1. Create a project at [supabase.com](https://supabase.com)
2. Run the schema migrations located in `apps/tracker/schema.sql` and `schema_v2.sql`.

### 3. Run BewerbLens Tracker
```bash
cd apps/tracker
python -m venv .venv
source .venv/bin/activate
pip install -e .
python tracker.py
```

### 4. Run the Dashboard
```bash
cd apps/dashboard
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### 4. Run n8n (Optional)

```bash
docker compose up -d
```

Access n8n at [http://localhost:5678](http://localhost:5678). Import the workflow from `job_tracker_workflow_fixed.json`.

---

## How the Pipeline Works

```
Step 1: Checkpoint ── Read last processed date from Supabase
         │
Step 2: Fetch ──────── Query Gmail API for emails since checkpoint
         │
Step 3: Bronze Ingest ─ Store raw emails for audit trail
         │
Step 4: Pre-Filter ──── Rule-based filtering (blocked senders, patterns)
         │
Step 5: Deduplicate ─── Compare thread_ids against existing database
         │
Step 6: Classify ────── Gemini AI classifies each new email
         │
Step 7: Upsert ──────── Insert or update in Supabase with status priority
         │
Step 8: Notify ──────── Send Telegram alert for new/updated applications
         │
Step 9: Log ─────────── Record processing details for auditing
```

---

## Deployment

### GitHub Actions (Free)

The tracker can run automatically every 4 hours on GitHub Actions:

1. Push to a **private** GitHub repository
2. Add these secrets in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `GMAIL_CREDENTIALS_JSON` | Base64-encoded `credentials.json` |
| `GMAIL_TOKEN_JSON` | Base64-encoded `token.json` |
| `GEMINI_API_KEY` | Your Gemini API key |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase service_role key |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (optional) |
| `TELEGRAM_CHAT_ID` | Telegram chat ID (optional) |

### Dashboard Deployment

Deploy the Next.js dashboard to **Vercel** (recommended):

```bash
npx vercel
```

Or any platform supporting Next.js (Railway, Render, etc.).

---

## Why Python Over n8n?

| Problem in n8n | Solution in Python |
|---|---|
| 4 monthly Gmail API calls every run | Single incremental `after:` query |
| In-memory cache lost on restart | Supabase `UNIQUE` constraint on `thread_id` |
| ~255 Gemini batches on first run | Same batching, but with `tenacity` retries |
| Fragile JSON parsing in Code nodes | Pydantic enforced schemas |
| Visual debugging nightmare | Structured logging with `loguru` |
| No persistent state | Postgres checkpoint (last processed date) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11+, TypeScript 5 |
| **AI** | Google Gemini (3.1 Flash Lite / 3 Flash / 3.1 Pro) |
| **Backend** | Supabase (PostgreSQL) |
| **Frontend** | Next.js 16, React 19, Recharts 3 |
| **Styling** | CSS Modules, next-themes |
| **Auth** | Supabase Auth |
| **Notifications** | Telegram Bot API |
| **CI/CD** | GitHub Actions |
| **Infrastructure** | Docker Compose, n8n |

---

## License

MIT — See [LICENSE](LICENSE) for details.

---

## Author

**Maher Ahmed Raza** — [GitHub](https://github.com/maherahmedraza)

---

> *BewerbLens turns the chaos of job hunting into clarity. Every application tracked, every response captured, every opportunity visible.*
