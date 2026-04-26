# System Architecture

BewerbLens is built as a modular system consisting of three main applications working together with Supabase as the central data and coordination hub.

## Production Hosting

| Layer | Platform | Details |
|---|---|---|
| **Frontend** | Vercel (Free) | Next.js SSR + Global Edge CDN, auto-deploy from `main` |
| **Backend** | DigitalOcean App Platform ($5/mo) | Docker container running FastAPI + Worker |
| **Database** | Supabase (Free) | PostgreSQL + Auth + RLS + Realtime |
| **CI/CD** | GitHub Actions | Lint → Test → Build → Deploy (path-filtered) |

The backend runs from a `Dockerfile` at the project root, which copies `apps/tracker` and `apps/orchestrator` into a Python 3.12 slim image and sets `PYTHONPATH` for cross-module imports.

## High-Level Components

### 1. Orchestrator Service (`apps/orchestrator`)
A FastAPI-based service that acts as the brain of the system.
- **Scheduler**: Uses `APScheduler` (`AsyncIOScheduler`) to trigger periodic synchronisation tasks. Reads `schedule_interval_hours` from the `pipeline_config` table on startup and whenever the config is updated. Supports dynamic pause/resume without a restart.
- **REST API**: Provides endpoints for the dashboard to trigger runs, fetch history, cancel active runs, resume failed/cancelled runs, rerun from a selected stage, and update configuration.
- **Worker**: A daemon thread running `worker_loop`, which polls the `pipeline_tasks` queue via the `claim_next_task` Supabase RPC, executes the tracker pipeline, and writes results back to `pipeline_runs`.
- **Zombie Cleanup**: A secondary APScheduler job runs `HeartbeatMonitor.cleanup_zombies()` every 5 minutes to detect and mark stale runs as `failed`.

### 2. AI Tracker Pipeline (`apps/tracker`)
The core processing engine written in Python 3.11+.
- **Multi-user**: `run_pipeline_multiuser()` accepts a `user_id` and loads that user's Gmail credentials, email filters, and Telegram settings from Supabase.
- **Ingestion**: Connects to the Gmail API using incremental checkpointing (only fetching emails since the last run). Applies per-user rule-based email filters from the `email_filters` table.
- **Classification**: A `ClassifierFactory` selects the active classifier implementation based on the `CLASSIFIER_PROVIDER` setting (default: `gemini`). The `GeminiClassifier` defaults to Gemini 3.1 Flash-Lite and uses Structured Outputs / JSON Schema plus `tenacity` retries.
- **Fuzzy Matching**: `ApplicationMatcher` (`fuzzy_matcher.py`) resolves naming inconsistencies between job portals and email senders using composite similarity scoring.
- **Persistence**: `upsert_application_fixed` applies Status Priority Logic (terminal states like Offer or Rejected are never downgraded).
- **Notifications**: Sends a **consolidated end-of-run Telegram report** (added/updated/skipped/error counts, company names, duration) instead of per-job spam messages.
- **Failure Resilience** (`failure_handler.py`):
  - `@with_retry` decorator — exponential backoff (configurable max attempts, initial delay, max delay).
  - `HeartbeatMonitor` — detects zombie runs (no heartbeat for > 10 minutes) and marks them `failed`.
  - `StepExecutor` — executes pipeline steps with automatic DB state management and optional rollback.
  - `PartialSuccessHandler` — saves partial results when individual emails fail, preventing total loss.
- **Pipeline Logger** (`pipeline_logger.py`): `PipelineLogger` buffers log entries (default 50 entries or 5 seconds) before batch-inserting to `pipeline_run_logs`, reducing DB write load by ~90%.

### 3. Dashboard Frontend (`apps/dashboard`)
A Next.js 16 application using the App Router.
- **Layout**: `AppShell` client component switches between a public layout (no sidebar/header for `/` and `/login`) and the authenticated app container with sidebar and header.
- **Landing Page** (`/`): Public page with feature highlights, trust stats, and auth-aware CTA. No sidebar or header chrome.
- **Dashboard** (`/dashboard`): Authenticated operational overview — spotlight cards, quick actions, pipeline health signals, top companies, and location mix.
- **Analytics** (`/analytics`): Single analytics hub — insight cards, monthly trends, conversion funnel, platform breakdown, **Sankey status flow** chart (custom Recharts component with typed nodes/links), and usage analytics.
- **Settings** (`/settings`): Unified workspace — sync controls, pipeline configuration, GDPR export/delete, account details, integrations (Gmail OAuth, Telegram linking), and email filters. `/profile` redirects here.
- **Pipeline Page**: Three-panel layout — `PipelineMonitor` (live stage progress + run controls), `ExecutionHistory` (paginated run table with log drawer and resume/stop actions), and `ConfigPanel` (pause/resume scheduler, sync interval, log retention).
- **Realtime**: `usePipeline.ts` hooks use Supabase Realtime (Postgres Changes) to subscribe to `pipeline_runs`, `pipeline_run_steps`, and `pipeline_config` tables. The UI updates without polling.
- **Optimistic UI**: `useUpdateConfig` applies config changes locally before the API call completes, rolling back on error.
- **Design System**: Uses Instrument Sans (body), Fraunces (display), and IBM Plex Mono for typography. Glassmorphic surfaces with semi-transparent backgrounds, large diffused shadows, and 24px border radii.

---

## Data Flow (The "Medallion" Pipeline)

BewerbLens follows a simplified "Medallion" data architecture:

1. **Bronze (Raw Emails)**:
   - Raw email metadata and previews are stored in the `raw_emails` table (with `user_id`).
   - Serves as an audit trail and allows re-processing if AI logic improves.
   - Deduplicated natively via `UNIQUE` constraint on `email_id`.

2. **Silver (Classified Applications)**:
   - The AI processes Bronze data in three tracked stages: **Ingestion → Analysis → Persistence**.
   - Structured records are created in the `applications` table (with `user_id`).
   - Updates use **Status Priority Logic** — an "Interview" status cannot be overwritten by a late "Application Confirmation".

3. **Gold (Analytics & UI)**:
   - Aggregated via Supabase views (`application_stats`) and surfaced in the Dashboard.
   - Per-user RLS policies ensure strict data isolation.

---

## Pipeline Stage Tracking

Each run creates three rows in `pipeline_run_steps` (one per stage). The dashboard polls these every 2 seconds while a run is active, and Supabase Realtime pushes updates instantly:

| Stage | `step_name` | Weight (progress bar) |
|---|---|---|
| Ingestion | `ingestion` | 33 % |
| Analysis | `analysis` | 33 % |
| Persistence | `persistence` | 34 % |

Each step tracks `status` (`pending` → `running` → `success` / `failed` / `skipped`), `progress_pct` (0–100), an optional `message`, and persisted `stats` artifacts. Those artifacts allow the worker to resume or rerun downstream stages without depending on in-memory state from the original task.

---

## Task Queue Workflow

1. **Trigger**: An event (scheduler or manual API call) calls `TrackerService.start_run()`.
2. **Create Run**: A record is inserted in `pipeline_runs`; three step rows are seeded in `pipeline_run_steps`.
3. **Enqueue**: A task of type `"sync"` is inserted in `pipeline_tasks` with `parameters.start_stage`, allowing a new run, a resume, or a stage rerun to all share the same worker contract.
4. **Claim**: The background worker calls the `claim_next_task` Supabase RPC to atomically lock and claim the task.
5. **Heartbeat**: While running, a daemon thread updates `heartbeat_at` in `pipeline_runs` every 30 seconds.
6. **Execute**: `run_tracker_task()` → `run_pipeline_multiuser()` runs from the requested stage to the end, updating step progress in real time and persisting stage artifacts in `pipeline_run_steps.stats`.
7. **Log Sink**: Log entries are written directly to `pipeline_run_logs` (real-time) and buffered via `PipelineLogger` (batch).
8. **Finalise**: The worker marks `pipeline_tasks` as `done`/`failed` and updates `pipeline_runs` with `status`, `duration_ms`, and `summary_stats`.
9. **Zombie guard**: If the worker crashes, the scheduler's 5-minute cleanup job marks the run `failed`.

---

## Multi-User Architecture

All core tables (`applications`, `raw_emails`, `pipeline_runs`, `pipeline_tasks`, `pipeline_run_logs`) carry a `user_id` FK to `auth.users`. Row Level Security policies enforce that authenticated users can only read and write their own data.

| Table | RLS |
|---|---|
| `user_profiles` | Owner-only (SELECT / INSERT / UPDATE) |
| `applications` | Owner-only (SELECT / INSERT / UPDATE) |
| `raw_emails` | Owner-only (SELECT / INSERT) |
| `pipeline_runs` | Owner-only (SELECT / INSERT) |
| `pipeline_run_logs` | Derived from owning `pipeline_run` |
| `email_filters` | Owner-only (ALL) |

New users get a profile automatically via the `on_auth_user_created` trigger and can be initialised with region-appropriate default email filters via `initialize_user(user_id, region)`.

---

## Database Tables Summary

| Table | Purpose |
|---|---|
| `user_profiles` | Per-user Gmail/Telegram credentials, region, prefs |
| `email_filters` | Per-user include/exclude filter rules |
| `applications` | Deduplicated job applications |
| `raw_emails` | Bronze-layer email store |
| `pipeline_runs` | Run metadata (status, duration, summary_stats, heartbeat) |
| `pipeline_tasks` | Work queue consumed by the worker (`claim_next_task` RPC) |
| `pipeline_run_steps` | Per-stage progress tracking for each run |
| `pipeline_run_logs` | Structured log entries streamed to the dashboard |
| `pipeline_config` | Singleton config row (schedule_interval_hours, is_paused, retention_days) |
