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

**Gmail OAuth**
- `GMAIL_CREDENTIALS_JSON` — Full JSON string from Google Cloud Console
- `GMAIL_TOKEN_JSON` — Generated after running the OAuth flow
- `GMAIL_OAUTH_REDIRECT_URI`
- `ENCRYPTION_KEY` — Fernet key for encrypting stored Gmail tokens

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
   | `ENCRYPTION_KEY` | Secret |
   | `GEMINI_MODEL` | `gemini-3.1-flash-lite-preview` |
   | `BATCH_SIZE` | `10` |
   | `MIN_CONFIDENCE` | `0.55` |
6. Click **Create Resources**.

The app spec is also defined in `.do/app.yaml` for declarative configuration.

### 2.3 CI/CD Pipeline

Three GitHub Actions workflows automate the full pipeline:

| Workflow | File | Trigger | Purpose |
|---|---|---|---|
| **CI** | `ci.yml` | Every push & PR | Lint, test, build (reusable) |
| **Deploy Frontend** | `deploy.yml` | Push to `main` (dashboard changes) | Vercel production deploy |
| **Deploy Backend** | `deploy-backend.yml` | Push to `main` (backend changes) | DigitalOcean container deploy |
| **Pipeline Trigger** | `pipeline-trigger.yml` | Cron (every 4h) + manual | Insert sync task into Supabase |

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
| `SUPABASE_URL` | Supabase project settings | Pipeline trigger workflow |
| `SUPABASE_KEY` | Supabase service role key | Pipeline trigger workflow |
| `PIPELINE_USER_ID` | Your user UUID in Supabase | Pipeline trigger workflow |

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
4. **Cron verification**: Check GitHub Actions → `Scheduled Pipeline Sync` runs every 4 hours.
5. **Telegram**: If enabled, verify you receive a consolidated run summary after the pipeline completes.
