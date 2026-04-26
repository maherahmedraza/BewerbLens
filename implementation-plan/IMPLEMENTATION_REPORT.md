# Implementation Status Report

## Completed

### Phase 1 — Security hardening
- Replaced wildcard credentialed CORS with an allowlist.
- Added `ORCHESTRATOR_API_KEY` protection to `/runs/*` and `/config/*`.
- Moved browser orchestrator traffic behind the dashboard's same-origin server proxy.
- Added run ownership checks before cancel/resume/rerun actions are forwarded.
- Made backend startup fail closed when neither `ENCRYPTION_SECRET` nor `ENCRYPTION_KEY` is configured.
- Removed plaintext Gmail credential write fallback.
- Rewired consolidated Telegram run reports to use the shared bot token path.

### Phase 2 — Operational safety
- Added migration `013_pipeline_controls_and_followups.sql`.
- Added `pipeline_config.max_emails_per_run` and wired it through the orchestrator and dashboard settings UI.
- Capped large runs so emails are stored immediately but only the configured chunk is processed per run.
- Added scheduled retention cleanup for `pipeline_run_logs` and `usage_metrics`.
- Added reminder state on `applications.last_follow_up_reminder_at`.

### Phase 3 — Tracker maintainability
- Removed duplicated `record_usage_metrics()` call payloads behind a shared tracker helper.
- Added a pure helper for per-run email selection so fairness behavior is testable.

### Phase 4 — Testing and CI
- Added migration numbering validation in CI.
- Added dashboard component tests with Vitest.
- Added tracker runtime tests for encryption guards, follow-up reminder formatting, and run-cap prioritization.
- Extended CI with dashboard tests plus `pip-audit` and `npm audit`.

### Phase 5 — DevOps and preview environments
- Added `docker-compose.yml` for local dashboard + backend startup.
- Added `.do/app.dev.yaml` for a preview backend app.
- Added `deploy-backend-preview.yml` for `dev` branch backend deployments.

### Phase 6 — Product improvements
- Added Telegram follow-up reminders for stale `Applied` applications.
- Added dashboard `error.tsx` and `loading.tsx`.
- Improved chart accessibility labels and analytics modal semantics.
- Updated CSV export to stream a BOM-prefixed response for spreadsheet compatibility.

## Manual steps still required

1. Apply database migration `db/migrations/013_pipeline_controls_and_followups.sql` after migrations `001` through `012`.
2. Set the new environment variables in Vercel and DigitalOcean before deploying.
3. If you want backend preview deployments from `dev`, create a second DigitalOcean app from `.do/app.dev.yaml` and add its app ID as `DIGITALOCEAN_DEV_APP_ID`.
4. Run a real pipeline with a Telegram-linked user to confirm:
   - consolidated end-of-run reports arrive
   - backlog chunking behaves as expected
   - follow-up reminders arrive after the configured wait window
5. Merge `dev` into `main` only after preview validation is complete.

## Known follow-up note

- `npm audit` on the dashboard dependency tree still reports a **moderate** transitive `postcss` advisory through Next.js. CI now blocks **high** and **critical** production findings; keep tracking upstream Next.js releases so this moderate advisory can be cleared once a patched transitive chain is available.

## Required / important environment variables

| Variable | Where | Why |
| --- | --- | --- |
| `ORCHESTRATOR_API_KEY` | Vercel + DigitalOcean | Secures orchestrator writes and lets the dashboard proxy authenticate |
| `ENCRYPTION_SECRET` | Vercel + DigitalOcean | Preferred credential-encryption secret |
| `ENCRYPTION_KEY` | DigitalOcean only if still needed | Legacy fallback for older encrypted records |
| `SUPABASE_URL` | Vercel + DigitalOcean | Supabase project URL |
| `SUPABASE_KEY` | Vercel server routes + DigitalOcean | Service-role key for backend/server-only actions |
| `NEXT_PUBLIC_SUPABASE_URL` | Vercel | Browser Supabase URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Vercel | Browser Supabase anon key |
| `NEXT_PUBLIC_ORCHESTRATOR_URL` | Vercel | Public orchestrator base URL used by the server proxy fallback |
| `ORCHESTRATOR_URL` | Optional in Docker/dev/Vercel | Server-only override for private network routing |
| `ORCHESTRATOR_API_KEY` | DigitalOcean + Vercel | Shared secret used to authenticate the dashboard to the backend orchestrator |
| `GEMINI_API_KEY` | DigitalOcean | AI classification |
| `TELEGRAM_BOT_TOKEN` | DigitalOcean | Run summaries and follow-up reminders |
| `TELEGRAM_ENABLED` | DigitalOcean | Global notification gate |
| `FOLLOW_UP_REMINDER_DAYS` | DigitalOcean | Minimum age for stale `Applied` reminders |
| `FOLLOW_UP_REMINDER_REPEAT_DAYS` | DigitalOcean | Cooldown between repeated reminders |
| `GOOGLE_CLIENT_ID` | Vercel | Gmail OAuth start/callback |
| `GOOGLE_CLIENT_SECRET` | Vercel | Gmail OAuth token exchange |
| `GOOGLE_OAUTH_REDIRECT_URI` | Vercel | OAuth callback validation |
| `TELEGRAM_BOT_USERNAME` | Vercel | Telegram linking UX |
| `TELEGRAM_LINK_SECRET` | Vercel | Telegram link completion verification |
| `DIGITALOCEAN_DEV_APP_ID` | GitHub Actions | Optional preview backend deployment target |

## Recommended verification checklist

1. `python scripts/validate_migrations.py`
2. `ruff check apps/tracker apps/orchestrator`
3. `PYTHONPATH=apps/tracker pytest apps/tracker/tests -v --tb=short`
4. `cd apps/dashboard && npm run lint && npm run test && npm run build`
5. `docker compose up --build`
