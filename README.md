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
6. **Orchestrates** background tasks with a dedicated worker and scheduler

---

## Architecture

```mermaid
graph TD
    subgraph "External Services"
        Gmail[Gmail API]
        Gemini["Gemini 3.1 Flash-Lite<br/>(Structured Outputs)"]
        Telegram[Telegram Bot]
    end

    subgraph "User Interface"
        Dashboard[Next.js 16 Dashboard]
        AppTracker["Application Tracker<br/>(threaded view)"]
        PipelineMon["Pipeline Monitor<br/>(stage progress + controls)"]
        ProfilePage[Profile Page]
        Analytics[Analytics Hub<br/>Recharts]
        Dashboard --> AppTracker
        Dashboard --> PipelineMon
        Dashboard --> ProfilePage
        Dashboard --> Analytics
    end

    subgraph "API / Backend"
        Orchestrator["Orchestrator<br/>FastAPI + APScheduler"]
        Worker["Background Worker<br/>(claim_next_task RPC)"]
        TrackerSvc["TrackerService<br/>(start / cancel / resume / rerun)"]
        Orchestrator --> TrackerSvc
        TrackerSvc --> Worker
    end

    subgraph "Pipeline Stages"
        S1["Stage 1: Ingestion<br/>Gmail fetch + raw_emails"]
        S2["Stage 2: Analysis<br/>Gemini classification"]
        S3["Stage 3: Persistence<br/>fuzzy match + upsert"]
        S1 --> S2 --> S3
    end

    subgraph "Data Layer"
        DB[("Supabase / PostgreSQL")]
        RLS["Row Level Security<br/>(per-user isolation)"]
        DB --- RLS
    end

    Gmail --> S1
    S2 --> Gemini
    S3 --> Telegram
    S1 & S2 & S3 --> DB
    Worker --> S1
    Dashboard --> Orchestrator
    Dashboard --> DB
```

### Components

| Component | Tech Stack | Purpose |
|---|---|---|
| **Orchestrator** | FastAPI, APScheduler | REST API, job scheduling, and worker management |
| **Worker** | Python Threading | Background task execution (claims tasks via `claim_next_task` RPC) |
| **AI Tracker** | Python 3.11+, Gemini 3.1 Flash-Lite | Three-stage email ingestion, classification & persistence pipeline |
| **Dashboard** | Next.js 16, React 19, Recharts, TanStack Query | Real-time tracking UI with Supabase Realtime subscriptions |
| **Database** | Supabase (PostgreSQL) | Persistent storage, task queue, step tracking, RLS data isolation |

---

## Features

### System Orchestration
- **Real-time Monitoring** — Granular stage-level progress (Ingestion → Analysis → Persistence) shown live via Supabase Realtime.
- **Smart Scheduling** — Configurable interval (1 h – 24 h) stored in `pipeline_config`; dynamically updated without restart.
- **Pause / Resume** — Toggle the scheduler on/off from the dashboard without touching the server.
- **Run Controls** — Stop an active run, resume a failed/cancelled run, or rerun ingestion/analysis/persistence from the UI.
- **Manual Triggers** — Start a sync or backfill on-demand via the UI or API; returns immediately while execution continues asynchronously.
- **Multi-user** — Full per-user data isolation via Row Level Security; each user supplies their own Gmail credentials and email filter rules.

### AI Pipeline
- **Three-stage execution** — Ingestion, Analysis, and Persistence are tracked independently in `pipeline_run_steps` with per-step progress percentages.
- **Incremental Checkpointing** — Only processes new emails since the last successful run.
- **Gemini 3.1 Flash-Lite** — Default economical classifier model, requested with Structured Outputs / JSON Schema for robust parsing.
- **Fuzzy Matching** — Resolves company/job title naming inconsistencies across email threads and job portals.
- **Status Priority** — Terminal states (Offer, Rejected) are never overwritten by later lower-priority emails.
- **Zombie Detection** — Scheduler runs `HeartbeatMonitor` every 5 minutes to detect and kill stale runs.
- **Retry & Graceful Degradation** — Exponential-backoff retries; partial successes are saved rather than discarded.

### Premium Dashboard
- **Pipeline View** — Stage-by-stage progress bars, execution history table, config panel (pause, interval, retention), and per-run log drawer.
- **Analytics Hub** — Interactive charts for application trends and platform performance.
- **Modern UI** — Glassmorphic design, dark mode support, and responsive layouts.

---

## Project Structure

```
BewerbLens/
├── apps/                          # Core Applications
│   ├── orchestrator/              # FastAPI Task Manager
│   │   ├── main.py                # Entry point (lifespan, CORS, routers)
│   │   ├── routers/               # REST Endpoints (runs, config)
│   │   └── services/              # Worker, Scheduler, TrackerService, Config
│   │
│   ├── tracker/                   # AI Processing Pipeline
│   │   ├── tracker.py             # run_pipeline_multiuser() entry point
│   │   ├── classifier_factory.py  # Pluggable classifier (Gemini / future)
│   │   ├── classifier_base.py     # Abstract classifier interface
│   │   ├── gemini_classifier.py   # Gemini 3.1 Flash-Lite implementation
│   │   ├── fuzzy_matcher.py       # Company/job title deduplication
│   │   ├── failure_handler.py     # Retry, zombie detection, StepExecutor
│   │   ├── pipeline_logger.py     # Buffered DB log sink
│   │   ├── pre_filter.py          # Per-user rule-based email filtering
│   │   └── supabase_service.py    # DB operations (pipeline steps, heartbeat)
│   │
│   └── dashboard/                 # Next.js 16 Frontend
│       ├── src/app/               # App Router pages (pipeline, analytics, …)
│       ├── src/hooks/usePipeline.ts  # TanStack Query + Realtime hooks
│       └── src/components/        # UI Components (charts, tables, logs)
│
├── db/
│   └── migrations/                # Idempotent SQL migrations (run in order)
│
├── docs/                          # Detailed Documentation
│   ├── architecture.md            # System deep-dive
│   ├── api.md                     # Orchestrator API spec
│   ├── pipeline.md                # Pipeline stages & re-run guide
│   ├── deployment.md              # Setup & Hosting guides
│   └── troubleshooting.md         # Common issues & fixes
│
└── README.md                      # This file
```

---

## Quick Start

### 1. Prerequisites
- Python 3.11+ & Node.js 18+
- Supabase Project & Google Cloud Project (Gmail API + Gemini Key)

### 2. Environment Setup
```bash
cp .env.example .env
# Fill in your credentials — see docs/deployment.md for the full variable list
```

### 3. Apply Database Migrations
Run in order against your Supabase project:
```bash
psql "$DATABASE_URL" -f db/migrations/001_multiuser_foundation.sql
psql "$DATABASE_URL" -f db/migrations/002_hotfix_rls_policies.sql
psql "$DATABASE_URL" -f db/migrations/003_views_and_rls.sql
psql "$DATABASE_URL" -f db/migrations/004_application_stats_view.sql
psql "$DATABASE_URL" -f db/migrations/005_enable_realtime.sql
```

### 4. Start Backend Services
```bash
cd apps/orchestrator
pip install -e ../tracker   # install tracker as a package
python main.py              # FastAPI on port 8000
```

### 5. Start Dashboard
```bash
cd apps/dashboard
npm install && npm run dev
```

Visit `http://localhost:3000` to access the dashboard.

---

## Documentation

For more detailed information, please refer to the files in the `docs/` folder:
- [Architecture & Workflow](docs/architecture.md)
- [API Documentation](docs/api.md)
- [Pipeline Guide](docs/pipeline.md) — stages, re-run instructions, artifact persistence
- [Deployment Guide](docs/deployment.md)
- [Troubleshooting](docs/troubleshooting.md)

---

## License

MIT — See [LICENSE](LICENSE) for details.

---

## Author

**Maher Ahmed Raza** — [GitHub](https://github.com/maherahmedraza)
