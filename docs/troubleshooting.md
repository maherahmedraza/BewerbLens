# Troubleshooting Guide

Common issues and their resolutions.

## 1. Gmail Authentication Errors
**Symptoms**: `Auth error: Refresh token expired` or `401 Unauthorized`.
- **Cause**: Google Cloud OAuth tokens expire after 7 days in "Testing" mode.
- **Fix**: Re-run the local authentication script to generate a new `token.json`, encode it to Base64, and update your `.env` or GitHub Secrets.

## 2. Gemini AI Failures
**Symptoms**: `503 Service Unavailable` or `Classification failed`.
- **Cause**: Rate limits or temporary Google AI platform downtime.
- **Fix**: The tracker uses `tenacity` retries with exponential backoff automatically. Check the Orchestrator logs (or the Pipeline page log drawer) to see if it recovers. Verify your `GEMINI_API_KEY` is valid and not over quota.

## 3. Worker Not Claiming Tasks
**Symptoms**: Tasks stay in `"pending"` status in the `pipeline_tasks` table; run stays stuck in `"running"` on the dashboard.
- **Cause**: The background worker thread crashed or the Orchestrator isn't running.
- **Fix**:
  - Restart the Orchestrator service.
  - Check logs for Python tracebacks.
  - Verify the `claim_next_task` RPC function exists in Supabase (**Database → Functions**).

## 4. Zombie Runs
**Symptoms**: A run shows `"running"` status in the dashboard but no progress is made; heartbeat is stale.
- **Cause**: Worker crashed (OOM, network drop, infinite loop) without marking the run as failed.
- **Fix**: The scheduler automatically runs `HeartbeatMonitor.cleanup_zombies()` every 5 minutes. Runs with no heartbeat for > 10 minutes are marked `failed` automatically. You can also manually update the row via the Supabase SQL console:
  ```sql
  UPDATE pipeline_runs SET status = 'failed', ended_at = NOW() WHERE status = 'running';
  ```

## 5. Duplicate Applications
**Symptoms**: Same job appearing twice in the dashboard.
- **Cause**: Fuzzy matching threshold might be too permissive, or `thread_id` changed.
- **Fix**: Adjust the `company_threshold`, `job_threshold`, or `composite_threshold` in `ApplicationMatcher` (`apps/tracker/fuzzy_matcher.py`) or manually merge applications via the Supabase SQL console.

## 6. Dashboard Logs Empty
**Symptoms**: Log drawer shows nothing during or after a run.
- **Cause**: Real-time log sink failed due to Supabase rate limits or the run `id` was not passed to the pipeline correctly.
- **Fix**: Check the Orchestrator terminal output for the local log copy. Confirm the `pipeline_run_logs` table exists and has rows for the run's `id` (UUID, not `run_id` label). Also verify Supabase Realtime is enabled for the `pipeline_run_logs` table (migration `005_enable_realtime.sql`).

## 7. Scheduler Not Running or Wrong Interval
**Symptoms**: `/health` returns `"scheduler": false`; pipeline doesn't auto-trigger.
- **Cause**: Orchestrator failed to start the scheduler, or the `pipeline_config` singleton row is missing.
- **Fix**:
  - Call `GET /config/` — if it returns an empty object the config is missing; the service will auto-initialise it on the next call.
  - Call `PATCH /config/` with `{"is_paused": false, "schedule_interval_hours": 4.0}` to force a reschedule.
  - Restart the Orchestrator if the scheduler thread is completely dead.

## 8. Config Changes Not Taking Effect
**Symptoms**: Changed sync interval or paused the pipeline via the dashboard, but the scheduler still runs at the old interval.
- **Cause**: The scheduler reads `schedule_interval_hours` (a float, in hours). The old field name `sync_interval_minutes` no longer exists.
- **Fix**: Confirm the `pipeline_config` table has a `schedule_interval_hours` column. Re-apply migration `003_views_and_rls.sql` if the column is missing.

## 9. Stop / Resume / Rerun Controls Not Working
**Symptoms**: The Pipeline page shows control buttons, but the run does not stop, resume, or rerun from the selected stage.
- **Cause**: The Orchestrator service has not been restarted with the newer `/runs/{id}/cancel`, `/resume`, and `/rerun-stage` endpoints, or an old pending task is still in the queue.
- **Fix**:
  - Restart the Orchestrator so the updated routes and worker logic are loaded.
  - Confirm the run row in `pipeline_runs` has a valid `current_phase` and that `pipeline_run_steps` rows exist for `ingestion`, `analysis`, and `persistence`.
  - Check the run log drawer for `control` entries confirming that the stop/resume/rerun request was accepted.

---

## Production Deployment Issues

## 10. Vercel Build Fails
**Symptoms**: Deploy workflow fails at the "Build" step with `Module not found` or env var errors.
- **Cause**: Missing environment variables in the Vercel dashboard.
- **Fix**: Go to Vercel → Project Settings → Environment Variables and ensure `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_ORCHESTRATOR_URL` are set for the **Production** environment.

## 11. DigitalOcean Container Won't Start
**Symptoms**: DO app shows "Deploying" but never reaches "Active"; health check fails.
- **Cause**: Missing environment variables or the orchestrator crashes on startup.
- **Fix**:
  - Check the **Runtime Logs** tab in the DO dashboard for Python tracebacks.
  - Verify all required env vars are set: `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY`, `ENCRYPTION_KEY`.
  - Test the Docker image locally: `docker build -t bewerblens . && docker run -p 8000:8000 --env-file .env bewerblens`

## 12. GitHub Actions Deploy Fails
**Symptoms**: CI passes but `deploy-backend.yml` fails at "Trigger deployment".
- **Cause**: `DIGITALOCEAN_ACCESS_TOKEN` or `DIGITALOCEAN_APP_ID` secrets are missing or expired.
- **Fix**:
  - Go to GitHub → Settings → Secrets → Verify both secrets exist.
  - Regenerate the DO token at [cloud.digitalocean.com/account/api/tokens](https://cloud.digitalocean.com/account/api/tokens) if expired.

## 13. CORS Errors in Production
**Symptoms**: Dashboard shows network errors; browser console shows `Access-Control-Allow-Origin` blocked.
- **Cause**: The orchestrator's CORS middleware needs to allow your Vercel domain.
- **Fix**: Update `allow_origins` in `apps/orchestrator/main.py` to include your production URL instead of `"*"`.

## 14. Pipeline Trigger Cron Not Working
**Symptoms**: No pipeline runs appear every 4 hours; `Scheduled Pipeline Sync` workflow shows no recent runs.
- **Cause**: Missing `SUPABASE_URL`, `SUPABASE_KEY`, or `PIPELINE_USER_ID` GitHub secrets.
- **Fix**: Verify all three secrets are set in GitHub → Settings → Secrets. You can test manually via the **workflow_dispatch** trigger.

