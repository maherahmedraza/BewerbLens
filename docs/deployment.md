# Deployment Guide

BewerbLens uses a **hybrid cloud architecture**: Vercel for the frontend, DigitalOcean App Platform for the backend, and Supabase for the database.

---

## 1. Local Development

### Environment Variables
Create a `.env` file in the root directory based on `.env.example`. Required keys:

**Supabase & AI**
- `SUPABASE_URL` & `SUPABASE_KEY` (service-role key)
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (default: `gemini-3.1-flash-lite-preview`)

**Dashboard server routes**
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`
- `TELEGRAM_BOT_USERNAME`
- `TELEGRAM_LINK_SECRET`
- `ENCRYPTION_SECRET` (preferred) or `ENCRYPTION_KEY` (legacy fallback)

**Gmail OAuth fallback**
- `GMAIL_CREDENTIALS_JSON` — optional legacy bootstrap JSON
- `GMAIL_TOKEN_JSON` — optional legacy token JSON for local single-user runs

**Telegram** (optional, per-user settings stored in Supabase take precedence)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

**Dashboard**
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_ORCHESTRATOR_URL` (default: `http://localhost:8000`)

---

### Database Setup
Run all migrations **in order** against your Supabase project. All migrations are idempotent.

```bash
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
```

Alternatively, paste each file into the Supabase **SQL Editor** and click **Run**.

After applying migrations, ensure the `claim_next_task` RPC function is present (created in the base schema). Confirm via **Database → Functions** in the Supabase dashboard.

---

### Backend (Orchestrator & Tracker)
```bash
pip install -r requirements.txt     # Install all Python dependencies
cd apps/orchestrator
python main.py                      # FastAPI on port 8000
```
The API will be available at `http://localhost:8000`. The worker thread and scheduler start automatically.

### Frontend (Dashboard)
```bash
cd apps/dashboard
npm install && npm run dev          # Next.js on port 3000
```

The `next.config.ts` automatically loads environment variables from the root `.env` during local development.

---

## 2. Production Deployment

### Architecture Overview

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   Vercel (Free)  │────▶│ DigitalOcean ($5/mo)  │────▶│ Supabase (Free) │
│   Next.js SSR    │     │  Docker Container     │     │   PostgreSQL    │
│   Global CDN     │     │  FastAPI + Worker      │     │   Auth + RLS    │
└─────────────────┘     └──────────────────────┘     │   Realtime      │
                                                      └─────────────────┘
```

### 2.1 Frontend → Vercel

1. Go to [vercel.com/new](https://vercel.com/new) and import `maherahmedraza/BewerbLens`.
2. Set **Root Directory** to `apps/dashboard`.
3. Add environment variables in the Vercel dashboard:
   | Variable | Value |
   |---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Your Supabase anon key |
   | `NEXT_PUBLIC_ORCHESTRATOR_URL` | Your DigitalOcean app URL |
   | `GOOGLE_CLIENT_ID` | Google OAuth client ID |
   | `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
   | `GOOGLE_OAUTH_REDIRECT_URI` | Usually `https://<your-app>/api/integrations/google/callback` |
   | `SUPABASE_KEY` | Supabase service-role key for the Telegram link completion route |
   | `ENCRYPTION_SECRET` | Shared secret used to encrypt Gmail credentials before persisting them |
   | `TELEGRAM_BOT_USERNAME` | Public username of your Telegram bot |
   | `TELEGRAM_LINK_SECRET` | Shared secret expected by `/api/integrations/telegram/link/complete` |
4. Click **Deploy**.

> **Note**: The `next.config.ts` is configured with dual-mode env loading — it uses `dotenv` locally but skips it on Vercel/CI where environment variables are injected by the platform.

### 2.2 Backend → DigitalOcean App Platform

1. Go to [cloud.digitalocean.com/apps/new](https://cloud.digitalocean.com/apps/new).
2. Select **GitHub** → Choose `BewerbLens` → Branch: `main`.
3. DigitalOcean will auto-detect the `Dockerfile` at the root.
4. Configure the component:
   - **Name**: `orchestrator`
   - **Resource Size**: Basic ($5/mo) — 1 vCPU, 0.5 GB RAM
   - **Region**: Frankfurt (FRA) for Europe
5. Add environment variables (mark secrets as encrypted):
   | Variable | Type |
   |---|---|
   | `SUPABASE_URL` | Secret |
    | `SUPABASE_KEY` | Secret |
    | `GEMINI_API_KEY` | Secret |
    | `ENCRYPTION_SECRET` | Secret |
    | `ENCRYPTION_KEY` | Secret (legacy fallback) |
    | `GEMINI_MODEL` | `gemini-3.1-flash-lite-preview` |
    | `BATCH_SIZE` | `50` |
    | `MIN_CONFIDENCE` | `0.55` |
    | `GMAIL_DAILY_QUOTA_UNITS` | `1000000000` |
    | `GEMINI_INPUT_COST_PER_MILLION` | `0.10` |
    | `GEMINI_OUTPUT_COST_PER_MILLION` | `0.40` |
6. Click **Create Resources**.

The app spec is also defined in `.do/app.yaml` for declarative configuration.

### 2.3 CI/CD Pipeline

Three GitHub Actions workflows automate CI and deployment:

| Workflow | File | Trigger | Purpose |
|---|---|---|---|
| **CI** | `ci.yml` | Every push & PR | Lint, test, build (reusable) |
| **Deploy Frontend** | `deploy.yml` | Push to `main` (dashboard changes) | Vercel production deploy |
| **Deploy Backend** | `deploy-backend.yml` | Push to `main` (backend changes) | DigitalOcean container deploy |

#### Required GitHub Secrets

| Secret | Source | Purpose |
|---|---|---|
| `VERCEL_TOKEN` | [vercel.com/account/tokens](https://vercel.com/account/tokens) | Vercel CLI authentication |
| `VERCEL_ORG_ID` | `.vercel/project.json` after `npx vercel link` | Identifies your Vercel account |
| `VERCEL_PROJECT_ID` | `.vercel/project.json` after `npx vercel link` | Identifies the project |
| `DIGITALOCEAN_ACCESS_TOKEN` | [DO API → Tokens](https://cloud.digitalocean.com/account/api/tokens) | doctl authentication |
| `DIGITALOCEAN_APP_ID` | DO dashboard URL after app creation | Target app for deployment |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project settings | CI build env var |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase project settings | CI build env var |
| `NEXT_PUBLIC_ORCHESTRATOR_URL` | DigitalOcean app URL | CI build env var |

#### Deploy Flow

```
git push to main
    │
    ├── CI (ci.yml) runs first
    │   ├── Backend: ruff check + pytest
    │   ├── Dashboard: eslint + next build
    │   └── Security: Gitleaks scan
    │
    ├── Deploy Frontend (deploy.yml) — only if apps/dashboard/** changed
    │   └── vercel build --prod → vercel deploy --prebuilt --prod
    │
    └── Deploy Backend (deploy-backend.yml) — only if apps/tracker/** or apps/orchestrator/** changed
        └── doctl apps create-deployment <APP_ID> --wait
```

---

## 3. Post-Deployment Verification

1. **Backend health**: `GET https://<your-do-app>.ondigitalocean.app/health`
   - Expect: `{"status": "ok", "worker": "active", "scheduler": true}`
2. **Frontend**: Visit your Vercel URL → Login → Navigate to Pipeline page.
3. **Manual sync**: Click **Manual Sync** on the Pipeline page → Watch stage progress bars animate.
4. **Scheduler verification**: Confirm the backend reports `"scheduler": true` on `/health`, then wait for the configured interval or trigger a manual run from the dashboard.
5. **Telegram**: Generate a link code in the Profile page, complete the bot handshake, and verify you receive a consolidated run summary after the pipeline completes.
