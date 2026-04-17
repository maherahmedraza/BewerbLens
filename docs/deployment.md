# Deployment Guide

BewerbLens can be deployed locally for development or hosted in the cloud for continuous tracking.

## 1. Local Development

### Environment Variables
Create a `.env` file in the root directory based on `.env.example`. Required keys:

**Supabase & AI**
- `SUPABASE_URL` & `SUPABASE_KEY` (service-role key)
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (default: `gemini-3.1-flash-lite-preview`)

**Gmail OAuth** (Base64-encoded JSON files)
- `GMAIL_CREDENTIALS_JSON`
- `GMAIL_TOKEN_JSON`
- `GMAIL_OAUTH_REDIRECT_URI`
- `ENCRYPTION_KEY`

**Classifier** (optional, defaults to `gemini`)
- `CLASSIFIER_PROVIDER=gemini`

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
1. Install tracker as a local package:
   ```bash
   pip install -e ./apps/tracker
   ```
2. Run the Orchestrator:
   ```bash
   cd apps/orchestrator
   python main.py
   ```
   The API will be available at `http://localhost:8000`. The worker thread and scheduler start automatically.

### Frontend (Dashboard)
1. Install dependencies:
   ```bash
   cd apps/dashboard
   npm install
   ```
2. Start the development server:
   ```bash
   npm run dev
   ```

---

## 2. Production Deployment

### Backend (Docker)
Use the provided `docker-compose.yml` to run the services in the background:
```bash
docker compose up -d
```

### Frontend (Vercel)
The dashboard is optimised for Vercel:
1. Connect your GitHub repository to Vercel.
2. Set the root directory to `apps/dashboard`.
3. Add all required environment variables in the Vercel Dashboard, including `NEXT_PUBLIC_ORCHESTRATOR_URL` pointing to your hosted Orchestrator.
4. Deploy.

### GitHub Actions (Serverless Tracker)
If you prefer not to host a 24/7 server, run the tracker via GitHub Actions (cron job):
- See `.github/workflows/tracker.yml` for configuration.
- Note: This bypasses the Orchestrator and runs the sync script directly. The Pipeline page in the dashboard will not reflect these runs unless you write results to Supabase manually.

---

## 3. Post-Deployment Verification
1. Call `GET /health` on the Orchestrator and confirm `"status": "ok"` and `"scheduler": true`.
2. Open the Dashboard → **Pipeline** page and click **Manual Sync** to test the Gmail/Gemini integration.
3. Watch the stage progress bars (Ingestion → Analysis → Persistence) advance in real time.
4. Verify the **Stop Run**, **Resume Run**, and **Rerun from Stage** controls appear as run state changes.
5. Check the **Execution History** table for a `success` result with non-zero `added`/`updated` stats.
