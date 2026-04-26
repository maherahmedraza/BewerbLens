# GitHub Copilot Instructions — BewerbLens

> **Scope**: These instructions apply to every file in this repository.
> Read this entire file before generating any code, migration, test, or config change.

---

## 1. Project Orientation

BewerbLens is an AI-powered, multi-user job-application tracker. It reads Gmail inboxes, classifies emails with Gemini AI, and surfaces structured pipeline data on a Next.js dashboard. The system is split across three deployable applications that share a single Supabase project as their coordination backbone.

```
BewerbLens/
├── apps/orchestrator/   # FastAPI control plane — REST API + APScheduler + worker thread
├── apps/tracker/        # Python AI pipeline — ingestion → analysis → persistence
├── apps/dashboard/      # Next.js 16 App Router frontend
├── db/migrations/       # Idempotent SQL files; run in numeric order (001 → latest)
├── .github/workflows/   # CI (ci.yml), deploy-frontend (deploy.yml), deploy-backend (deploy-backend.yml), cron (pipeline-trigger.yml)
├── .do/app.yaml         # DigitalOcean App Platform declarative spec
├── Dockerfile           # Root-level; builds orchestrator + tracker into one image
└── requirements.txt     # Single source of truth for ALL Python dependencies
```

**Production hosting**:
- Frontend → Vercel (Free Hobby Tier)
- Backend → DigitalOcean App Platform ($5/mo Docker container)
- Database → Supabase Free Tier (PostgreSQL + Auth + RLS + Realtime)
- CI/CD → GitHub Actions

---

## 2. Build, Test & Lint Commands

### Python Backend (`apps/tracker` + `apps/orchestrator`)

```bash
# Install dependencies — always from the root requirements.txt
pip install -r requirements.txt

# Lint — ruff is the only linter; do not add flake8, pylint, or black
ruff check apps/tracker apps/orchestrator

# Run all backend tests
PYTHONPATH=apps/tracker pytest apps/tracker/tests -v --tb=short

# Run a single test file
PYTHONPATH=apps/tracker pytest apps/tracker/tests/test_fuzzy_match.py -v --tb=short

# Run a single test by name
PYTHONPATH=apps/tracker pytest apps/tracker/tests/test_fuzzy_match.py::test_name -v --tb=short

# Build & validate the Docker image locally
docker build -t bewerblens .
docker run -p 8000:8000 --env-file .env bewerblens
```

### Dashboard (`apps/dashboard`)

```bash
cd apps/dashboard

# Install — always use ci (not install) to respect lockfile
npm ci

# Lint — ESLint only; do not add Prettier (it is not configured)
npm run lint

# Production build — requires the three NEXT_PUBLIC vars as shown
NEXT_PUBLIC_SUPABASE_URL=https://placeholder.supabase.co \
NEXT_PUBLIC_SUPABASE_ANON_KEY=placeholder_key \
NEXT_PUBLIC_ORCHESTRATOR_URL=http://localhost:8000 \
npm run build

# Local dev
npm run dev
```

### Database Migrations

```bash
# Run in strict numeric order — all files are idempotent
psql "$DATABASE_URL" -f db/migrations/001_multiuser_foundation.sql
psql "$DATABASE_URL" -f db/migrations/002_hotfix_rls_policies.sql
psql "$DATABASE_URL" -f db/migrations/003_views_and_rls.sql
psql "$DATABASE_URL" -f db/migrations/004_application_stats_view.sql
psql "$DATABASE_URL" -f db/migrations/005_enable_realtime.sql
psql "$DATABASE_URL" -f db/migrations/006_fix_status_enum_strings.sql
psql "$DATABASE_URL" -f db/migrations/007_remove_thread_id_unique.sql
psql "$DATABASE_URL" -f db/migrations/008_fix_pipeline_runs_constraints.sql
psql "$DATABASE_URL" -f db/migrations/009_reset_for_reprocessing.sql
psql "$DATABASE_URL" -f db/migrations/010_sync_integrations_analytics.sql
psql "$DATABASE_URL" -f db/migrations/011_fix_admin_role_policy_function.sql
psql "$DATABASE_URL" -f db/migrations/012_platform_allowlist_gmail_legacy_and_locations.sql
```

---

## 3. Architecture Rules

### 3.1 Supabase is the Central Coordination Hub

Supabase is not just a database. It serves four distinct roles simultaneously:

| Role | Mechanism | Used By |
|---|---|---|
| Auth & identity | `auth.users`, `auth.uid()` RLS helper | All three apps |
| Task queue | `pipeline_tasks` table + `claim_next_task` RPC | Orchestrator worker |
| Realtime transport | Postgres Changes subscriptions | Dashboard |
| Singleton config | `pipeline_config` row | Orchestrator scheduler + Dashboard |

**Never bypass Supabase for inter-service coordination.** Do not add Redis, RabbitMQ, or in-process shared state between the orchestrator and tracker.

### 3.2 Request Routing — Which App Handles What

| Action | Correct target | Incorrect |
|---|---|---|
| Trigger / cancel / resume a run | `POST /runs/...` on the orchestrator | Calling tracker directly |
| Read live run progress | Supabase Realtime subscription | Polling the orchestrator |
| Read analytics / application data | Supabase views directly from dashboard | Proxying through orchestrator |
| Update pipeline config | `PATCH /config/` on the orchestrator | Writing to Supabase from the dashboard |
| Fetch email / classify / persist | `apps/tracker` pipeline stages | Orchestrator doing classification |

### 3.3 Import Path Wiring

`apps/orchestrator/main.py` is the **only** place that adds `apps/tracker` to `sys.path`. Do not scatter `sys.path` hacks across other orchestrator modules. If a new orchestrator service file needs tracker code, import it — do not add another `sys.path` insertion.

---

## 4. Database Schema — Critical Reference

### 4.1 Identifier Conventions

| Identifier | Type | Meaning |
|---|---|---|
| `pipeline_runs.id` | UUID | **Canonical run ID** — use this in all FK relationships |
| `pipeline_runs.run_id` | Text | Human-readable label (`RUN-YYYYMMDD-HHMMSS-xxxxxx`) — for display only |
| `pipeline_run_steps.run_id` | UUID | Points to `pipeline_runs.id`, **not** `pipeline_runs.run_id` |
| `pipeline_run_logs.run_id` | UUID | Same — points to `pipeline_runs.id` |
| `pipeline_config.id` | UUID | Always `00000000-0000-0000-0000-000000000001` (singleton row) |

**Never** use `pipeline_runs.run_id` (the text label) as a foreign key target. Always use `pipeline_runs.id` (UUID).

### 4.2 Core Tables Overview

| Table | Key Columns | Notes |
|---|---|---|
| `user_profiles` | `id` (= `auth.users.id`), `gmail_credentials`, `telegram_chat_id`, `region` | Per-user credentials; Gmail token is Fernet-encrypted |
| `email_filters` | `id`, `user_id`, `filter_type`, `pattern`, `is_active` | Per-user include/exclude rules applied during ingestion |
| `applications` | `id`, `user_id`, `company_name`, `job_title`, `status`, `email_id` | Deduplicated; `status` follows priority rules |
| `raw_emails` | `id`, `user_id`, `email_id` (UNIQUE), `is_processed` | Bronze layer; `email_id` is the Gmail message ID |
| `pipeline_runs` | `id`, `run_id`, `user_id`, `status`, `current_phase`, `heartbeat_at`, `summary_stats` | Master run record |
| `pipeline_tasks` | `id`, `user_id`, `status`, `parameters` | Work queue; consumed via `claim_next_task` RPC |
| `pipeline_run_steps` | `id`, `run_id` (→ `pipeline_runs.id`), `step_name`, `status`, `progress_pct`, `stats` | One row per stage per run |
| `pipeline_run_logs` | `id`, `run_id` (→ `pipeline_runs.id`), `level`, `message`, `created_at` | Buffered via `PipelineLogger` |
| `pipeline_config` | singleton row | `schedule_interval_hours` (float), `is_paused` (bool), `retention_days` (int) |

### 4.3 Pipeline Run Status Lifecycle

```
pending → running → success
                 → failed
                 → cancelling → cancelled
```

Never write a status string not in this set. Never transition backwards (e.g., `failed` → `running` without creating a new run or using the resume endpoint).

### 4.4 Stage Step Names

The three `step_name` values are exactly: `ingestion`, `analysis`, `persistence`. They are always created in this order and always reference the same `pipeline_runs.id`.

### 4.5 `pipeline_run_steps.stats` — Artifact Contracts

Stages communicate via persisted JSON artifacts in `pipeline_run_steps.stats`. Never change these schemas without updating all downstream consumers.

| Stage | Stats model | Critical fields |
|---|---|---|
| `ingestion` | `IngestionStageStats` | `email_ids: list[str]`, `total_fetched`, `total_recovered`, `total_after_filters` |
| `analysis` | `AnalysisStageStats` | `email_ids: list[str]`, `classifications: dict[str, str]`, `total_classified` |
| `persistence` | `PersistenceStageStats` | `email_ids: list[str]`, `added`, `updated`, `skipped`, `errors` |

The `analysis` stage loads `email_ids` from **Ingestion's** persisted stats. The `persistence` stage loads from **both** Ingestion and Analysis stats. This is intentional — do not refactor these to use in-memory passing.

---

## 5. Multi-User & Security Rules

These rules are non-negotiable. Violating them creates data leaks between users.

### 5.1 Every Core Table Has `user_id`

All tables in section 4.2 carry a `user_id UUID NOT NULL REFERENCES auth.users(id)`. Every new table added to the schema must follow the same pattern.

### 5.2 RLS Is the Enforcement Boundary

Every table has Row Level Security enabled with policies in the form:

```sql
-- Owner-only read
CREATE POLICY "owner_select" ON table_name
  FOR SELECT USING (auth.uid() = user_id);

-- Owner-only write
CREATE POLICY "owner_insert" ON table_name
  FOR INSERT WITH CHECK (auth.uid() = user_id);
```

For tables derived from `pipeline_runs` (like `pipeline_run_steps`), the join pattern is used:

```sql
USING (
  EXISTS (
    SELECT 1 FROM pipeline_runs pr
    WHERE pr.id = pipeline_run_steps.run_id
      AND pr.user_id = auth.uid()
  )
)
```

**Never** create a policy with `USING (true)` or skip RLS on a user-data table. **Never** add a view that aggregates across `user_id` without filtering to the authenticated user.

### 5.3 Avoid RLS Recursion
Avoid defining RLS policies that call functions which in turn query the same table or call other policies. This causes infinite recursion. Instead:
- Use `SECURITY DEFINER` functions for role checks.
- Set the `search_path` to `public, auth` in those functions.
- Ensure the function itself is not governed by the policy it's helping to enforce.

### 5.4 SQL View Grouping Constraints
When creating views with `GROUP BY` that use `COALESCE` or other expressions for column normalization:
- Always group by the **entire expression** (e.g., `GROUP BY COALESCE(col, 'fallback')`) rather than just the column name.
- Avoid using column aliases in the `GROUP BY` clause if they conflict with base table column names.

### 5.5 Credentials Are Never Hardcoded

- Per-user Gmail tokens and Telegram `chat_id` live in `user_profiles`, encrypted at rest with a Fernet key (`ENCRYPTION_KEY` env var).
- Dashboard public env vars (`NEXT_PUBLIC_*`) are set on Vercel — not in source code.
- Backend secrets (`SUPABASE_KEY`, `GEMINI_API_KEY`, `ENCRYPTION_KEY`) are set on DigitalOcean App Platform as encrypted env vars — not in source code.
- CI secrets are in GitHub → Settings → Secrets — never in workflow YAML files directly.

### 5.4 Service Role Key Scope

`SUPABASE_KEY` is the **service role** key — it bypasses RLS. It is used **only** by the Python backend. The dashboard uses `NEXT_PUBLIC_SUPABASE_ANON_KEY`, which is subject to RLS. Never use the service role key in frontend code.

---

## 6. Pipeline Conventions (`apps/tracker`)

### 6.1 Stage Execution Order Is Fixed

The pipeline always runs `ingestion → analysis → persistence` in this order. Stages can be individually re-run or resumed, but order is immutable. Do not create shortcuts that skip stages.

### 6.2 Checkpointing & Ingestion Consistency
- **Ingestion fetches only emails since the last successful checkpoint** (`get_last_checkpoint`).
- **Recovery mode**: It also recovers previously unprocessed emails (`is_processed = false` in `raw_emails`).
- **Persistence Mandate**: ALL fetched emails must be inserted into `raw_emails` immediately upon ingestion, regardless of whether they pass the user filters. This prevents the "Infinite Fetch Loop" where the pipeline re-downloads the same spam/newsletter emails every run because they were never remembered as "processed".
- **No `is:unread`**: Never add `is:unread` to the Gmail search query in production incremental syncs. Deduplication is handled by the `raw_emails` table. Using `is:unread` causes emails to be lost forever if the user reads them on another device before the pipeline runs.

### 6.3 Classification-to-Status Mapping

`Classification` enum values from Gemini are **not** the same as `applications.status` values. Always convert through `CLASSIFICATION_TO_STATUS` in `gemini_classifier.py`. The valid input/output mapping is:

| Classification | → Status |
|---|---|
| `application_confirmation` | `Applied` |
| `positive_response` | `Interview` |
| `rejection` | `Rejected` |
| `not_job_related` | *(skip — do not persist)* |

### 6.4 Status Priority Rules — Never Downgrade

`applications.status` follows a strict priority hierarchy. `upsert_application_fixed` enforces this, but any new persistence code must also respect it:

```
Offer (100) > Rejected (99) > Interview > Applied
```

A record at `Offer` or `Rejected` can **never** be overwritten by any lower-priority classification from a later email. This is intentional — a rejection email arriving after an offer must not reset the status.

`ApplicationMatcher` in `fuzzy_matcher.py` uses composite similarity on `(company_name, job_title)`. 
- **Tolerance**: The `company_threshold` must be set to `0.70` (not 0.85). This handles variants like "Company" vs "Company GmbH" or "Company & Co.".
- **Logic**: The same company + same job title = update the existing record. The same company + different job title = new record. Do not bypass this with exact-string matching; company names differ across email senders and job portals.

### 6.6 Platform Allowlist Comes Before User Filters

Known job-platform sender addresses (`jobs-noreply@linkedin.com`, `noreply@xing.com`, `no-reply@stepstone.de`, `noreply@indeed.com`, `noreply@glassdoor.com`) must be modeled as protected `platform_allowlist` rows and evaluated before any include/exclude rule. Never let ordinary user filters block those senders.

### 6.7 Gemini Usage Must Be Persisted

Any classifier implementation must populate `last_usage` with `ai_requests`, input tokens, output tokens, and estimated cost. The tracker writes those values to both `usage_metrics` and `pipeline_runs.summary_stats`; do not return classifications without updating usage.

### 6.8 Gmail Legacy Fallback Must Be Explicit

If the tracker falls back to `GMAIL_TOKEN_JSON`, it must set `user_profiles.gmail_connected_via = 'env_fallback'`. Dashboard code must treat that as connected and show a legacy-mode warning instead of "Not connected".

### 6.9 Google OAuth Route Handlers

`/api/integrations/google/start` and `/api/integrations/google/callback` must stay on the Node.js runtime, validate `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_OAUTH_REDIRECT_URI`, and protect the callback with a signed state value. Do not allow uncaught OAuth exceptions to surface as raw 500 responses.

### 6.6 Telegram Notifications Are Consolidated

Do not send per-email Telegram messages. The `TelegramNotifier` sends a **single end-of-run summary** after `persistence` completes, containing added/updated/skipped/error counts and a company name list. Adding per-email notifications would spam users.

### 6.7 Retry & Resilience Decorators

- Use `@with_retry` from `failure_handler.py` for all external API calls (Gmail, Gemini, Telegram). The decorator applies exponential backoff with `tenacity`.
- Use `StepExecutor` from `failure_handler.py` when adding new pipeline stages. It handles DB state transitions and optional rollback automatically.
- Use `PartialSuccessHandler` when processing batches — save partial results rather than failing the entire batch.
- `HeartbeatMonitor.cleanup_zombies()` runs every 5 minutes via APScheduler. Runs with no `heartbeat_at` update for > 10 minutes are marked `failed`. Keep heartbeat updates in any long-running loop.

### 6.8 Pipeline Logger — Buffered Writes

`PipelineLogger` in `pipeline_logger.py` buffers log entries (default: 50 entries or 5 seconds) before batch-inserting to `pipeline_run_logs`. This reduces DB write load by ~90%. Do not write directly to `pipeline_run_logs` in a per-email loop — always use `PipelineLogger`.

---

## 7. Orchestrator Conventions (`apps/orchestrator`)

### 7.1 APScheduler — Dynamic Rescheduling

The scheduler reads `schedule_interval_hours` (a float, e.g. `4.0`) from the `pipeline_config` singleton on startup. When `/config/` is PATCHed, the scheduler reschedules itself dynamically — **no restart required**. The old column `sync_interval_minutes` no longer exists; do not reference it.

### 7.2 Worker — Task Claiming Contract

The worker calls the `claim_next_task` Supabase RPC to atomically lock tasks. Only one worker may claim a task. Do not use `SELECT ... FOR UPDATE` directly — the RPC handles this. The worker then calls `run_tracker_task()` → `run_pipeline_multiuser(user_id, ...)`.

### 7.3 Run Control Endpoints

| Endpoint | When to call | What it does |
|---|---|---|
| `POST /runs/trigger` | Manual or backfill | Creates a new `pipeline_runs` row and enqueues a task |
| `POST /runs/{id}/cancel` | Active run | Sets status to `cancelling`; worker detects and raises `PipelineCancelledError` |
| `POST /runs/{id}/resume` | Failed or cancelled run | Requeues from the first incomplete stage |
| `POST /runs/{id}/rerun-stage` | Specific stage failure | Resets the named stage and all downstream stages, then requeues |

Cancellation is **cooperative** — the worker checks status every 5 seconds. A cancel request does not kill the process immediately.

### 7.4 CORS Configuration

The CORS `allow_origins` list in `apps/orchestrator/main.py` must include the production Vercel URL. Do not use `"*"` in production — it opens the API to any origin.

---

## 8. Dashboard Conventions (`apps/dashboard`)

### 8.1 Styling — CSS Modules Only

The dashboard uses **Vanilla CSS Modules** (`.module.css` files). Do **not** add Tailwind CSS, styled-components, Emotion, or inline styles. Every new component needs a corresponding `.module.css` file in the same directory.

### 8.2 Auth & Session Protection

Auth and session protection is handled via `src/proxy.ts`. Do **not** add a `middleware.ts` file — it will conflict with the existing proxy setup. Check the installed Next.js 16 docs for App Router conventions before assuming behavior from older versions.

### 8.3 Data Fetching Strategy

| Data type | How to fetch | Do NOT do this |
|---|---|---|
| Live run/step/config updates | Supabase Realtime (`usePipeline.ts` hooks) | Poll the orchestrator API |
| Analytics & application data | Supabase views directly | Proxy through the orchestrator |
| Run control actions (trigger, cancel, resume, config update) | `fetch` → orchestrator REST API | Write directly to Supabase from the client |

### 8.4 TanStack Query + Realtime Pattern

`usePipeline.ts` combines TanStack Query for initial data fetch with Supabase Realtime subscriptions for live updates. When adding new subscribed tables, follow this exact pattern — do not introduce a separate polling interval alongside Realtime.

### 8.5 Status Normalization

Dashboard code must handle both Python enum repr strings (e.g., `"Classification.REJECTION"`) and display values (e.g., `"Rejected"`). Always use the normalization logic in `src/lib/status.ts`. Do not add ad-hoc `.toLowerCase()` or string-split hacks inline in components.

### 8.6 Optimistic UI Pattern

`useUpdateConfig` applies config changes locally before the API call completes and rolls back on error. Follow this pattern for any new mutation hooks — it prevents the UI from feeling sluggish on the $5/mo DigitalOcean instance.

### 8.7 Environment Variables

Only `NEXT_PUBLIC_*` variables are accessible in browser code. The three required variables are:

```
NEXT_PUBLIC_SUPABASE_URL       — set on Vercel
NEXT_PUBLIC_SUPABASE_ANON_KEY  — set on Vercel (anon key, not service role)
NEXT_PUBLIC_ORCHESTRATOR_URL   — set on Vercel (DigitalOcean app URL)
```

`next.config.ts` uses dual-mode env loading: `dotenv` locally, platform injection on Vercel/CI. Do not change this pattern.

### 8.8 Current Dashboard Information Architecture

- `/` is the public landing page.
- `/login` is public.
- `/dashboard` is the authenticated operational overview.
- `/analytics` is the single chart-heavy analytics hub.
- `/settings` is the primary workspace for account details, integrations, filters, sync controls, export, and destructive actions.
- `/profile` should not evolve as a second settings surface; redirect it to `/settings` instead of duplicating account-management UI.

---

## 9. CI/CD & Deployment Conventions

### 9.1 GitHub Actions Workflows

| Workflow | File | Trigger | Path filter |
|---|---|---|---|
| CI | `ci.yml` | Every push + PR | None (runs always) |
| Deploy Frontend Preview | `deploy-preview.yml` | Push to `dev` | `apps/dashboard/**` |
| Deploy Frontend | `deploy.yml` | Push to `main` | `apps/dashboard/**` |
| Deploy Backend | `deploy-backend.yml` | Push to `main` | `apps/tracker/**` or `apps/orchestrator/**` |
| Pipeline Cron | `pipeline-trigger.yml` | Schedule (every 4h) + `workflow_dispatch` | None |

Do not remove path filters — they prevent redundant deploys when only one app changes.

### 9.2 Branch Strategy

The repository workflow is intentionally two-branch:

- `dev` = integration, QA, and preview deployments
- `main` = production-only branch used by Vercel production, DigitalOcean production, and the main release workflows

CI should run on both `dev` and `main`. Production deploys stay pinned to `main`. Preview deploys belong on `dev`; do not repoint production workflows at `dev`.

### 9.3 Required GitHub Secrets

```
# Vercel
VERCEL_TOKEN
VERCEL_ORG_ID
VERCEL_PROJECT_ID

# DigitalOcean
DIGITALOCEAN_ACCESS_TOKEN
DIGITALOCEAN_APP_ID

# Dashboard build-time vars
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
NEXT_PUBLIC_ORCHESTRATOR_URL

# Pipeline cron trigger
SUPABASE_URL
SUPABASE_KEY
PIPELINE_USER_ID
```

Never add secrets as plain text in workflow YAML files. Always use `${{ secrets.SECRET_NAME }}`.

### 9.4 Python Dependency Changes

If you add, remove, or upgrade a Python package, update **only** the root `requirements.txt`. Do not update `apps/tracker/pyproject.toml` only — Docker and CI use the root file. Both files must be kept in sync if `pyproject.toml` is also maintained.

### 9.5 DigitalOcean App Spec

`.do/app.yaml` is the declarative spec for the DigitalOcean backend. If the container port, run command, resource size, or env var names change, update this file alongside the orchestrator code.

---

## 10. Testing Conventions

### 10.1 Backend Tests

- Test files live at `apps/tracker/tests/` and must be named `test_*.py`.
- Always run with `PYTHONPATH=apps/tracker` to match the production import environment.
- Use `pytest` with fixtures; do not use `unittest.TestCase`.
- Mock external calls (Gmail API, Gemini, Supabase, Telegram) — tests must not require live credentials.
- Use `pytest-asyncio` for any async test functions.

### 10.2 Frontend Tests

- Test files are colocated with source files and named `*.test.ts` / `*.test.tsx`.
- Use Vitest + React Testing Library.
- Do not import Supabase or orchestrator clients directly in tests — mock them at the module boundary.

---

## 11. Explicit Anti-Patterns

These are the most common mistakes to avoid. Each one has caused a real bug or architectural regression.

| ❌ Anti-pattern | ✅ Correct approach |
|---|---|
| Treating `/profile` and `/settings` as two independent settings products | Keep `/settings` as the single workspace and redirect `/profile` |
| Packing Sankey/funnel/monthly charts into `/dashboard` and `/analytics` simultaneously | Keep `/dashboard` operational and `/analytics` as the dedicated analytics hub |
| Running CI only on `main` while using `dev` as the shared test branch | Run CI on both `dev` and `main` |
| Expecting Telegram delivery while `TELEGRAM_ENABLED` is false in runtime config | Keep Telegram enabled in backend runtime when bot delivery is intended |
| Using `pipeline_runs.run_id` (text) as a FK | Use `pipeline_runs.id` (UUID) |
| Referencing `sync_interval_minutes` | Use `schedule_interval_hours` (float) |
| Writing `middleware.ts` in the dashboard | Use the existing `src/proxy.ts` |
| Using Tailwind CSS in dashboard components | Use Vanilla CSS Modules (`.module.css`) |
| Bypassing `CLASSIFICATION_TO_STATUS` for status writes | Always convert through that mapping |
| Writing an `applications.status` downgrade (e.g., Offer → Applied) | Respect the priority hierarchy; use `upsert_application_fixed` |
| Adding `sys.path` hacks in orchestrator services | Only `apps/orchestrator/main.py` does path wiring |
| Sending per-email Telegram messages | Only send a consolidated end-of-run summary |
| Updating only `apps/tracker/pyproject.toml` for new Python packages | Update root `requirements.txt` too |
| Calling `claim_next_task` with raw SQL instead of the RPC | Always use the Supabase RPC |
| Creating new Supabase views without `user_id` filtering | Every view must filter to `auth.uid()` |
| Storing secrets in workflow YAML or source code | Use platform env vars and GitHub Secrets |
| Using `SUPABASE_KEY` (service role) in frontend code | Frontend uses only `NEXT_PUBLIC_SUPABASE_ANON_KEY` |
| Polling the orchestrator for live run updates | Use Supabase Realtime subscriptions |
| Using `"*"` in CORS `allow_origins` in production | Explicitly list the Vercel production URL |
| Sending log entries per-email to `pipeline_run_logs` | Use `PipelineLogger` for buffered batch writes |
| In-memory state sharing between pipeline stages | Persist all stage output in `pipeline_run_steps.stats` |
| Calling tracker code directly from the dashboard | All write operations go through the orchestrator REST API |
| Hard-coding `pipeline_config` ID as a string literal more than once | The ID is `00000000-0000-0000-0000-000000000001`; define it once as a constant |
| Using `is:unread` in Gmail incremental queries | Rely on `raw_emails` deduplication; never use `is:unread` |
| Filtering emails *before* saving them to `raw_emails` | Always save fetched emails to `raw_emails` before filtering |
| Defining RLS policies that call each other | Use `SECURITY DEFINER` functions to avoid recursion |
| Using `secrets: inherit` in `on: workflow_call` definitions | Use `secrets: inherit` only when *calling* a workflow |
| Setting `company_threshold > 0.70` in `ApplicationMatcher` | Keep it at 0.70 to handle "GmbH" and "& Co." variants |
| Grouping by column name in SQL when using `COALESCE` | Group by the full `COALESCE(...)` expression |
