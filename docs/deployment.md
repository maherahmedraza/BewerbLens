# Deployment Guide

BewerbLens can be deployed locally for development or hosted in the cloud for continuous tracking.

## 1. Local Development

### Environment Variables
Create a `.env` file in the root directory based on `.env.example`. Required keys:

- `SUPABASE_URL` & `SUPABASE_KEY`
- `GEMINI_API_KEY`
- `GMAIL_CREDENTIALS_JSON` (Base64 encoded)
- `GMAIL_TOKEN_JSON` (Base64 encoded)

### Backend (Orchestrator & Tracker)
1. Install dependencies:
   ```bash
   pip install -e ./apps/tracker
   ```
2. Run the Orchestrator:
   ```bash
   cd apps/orchestrator
   python main.py
   ```

### Frontend (Dashboard)
1. Install dependencies:
   ```bash
   cd apps/dashboard
   npm install
   ```
2. Start development server:
   ```bash
   npm run dev
   ```

---

## 2. Production Deployment

### Database (Supabase)
- Ensure all migrations in `apps/tracker/migrations` have been applied.
- Set up the `claim_next_task` RPC function in the database (SQL provided in migrations).

### Backend (Docker)
Use the provided `docker-compose.yml` to run the services in the background:
```bash
docker compose up -d
```

### Frontend (Vercel)
The dashboard is optimized for Vercel:
1. Connect your GitHub repository to Vercel.
2. Add the environment variables in the Vercel Dashboard.
3. Deploy!

### GitHub Actions (Alternative Tracker)
If you don't want to host a 24/7 server, you can run the tracker via GitHub Actions (as a cron job).
- See `.github/workflows/tracker.yml` for configuration.
- Note: This bypasses the Orchestrator and runs the sync directly.

---

## 3. Post-Deployment Verification
1. Access the Dashboard and go to the **Profile** page to verify Supabase connectivity.
2. Go to the **Pipeline** page and click "Start Sync" to test the Gmail/Gemini integration.
3. Check the real-time logs in the dashboard to ensure no errors occur.
