# Troubleshooting Guide

Common issues and their resolutions.

## 1. Gmail Authentication Errors
**Symptoms**: `Auth error: Refresh token expired` or `401 Unauthorized`.
- **Cause**: Google Cloud OAuth tokens usually expire every 7 days in "Testing" mode.
- **Fix**: Re-run the local authentication script to generate a new `token.json`, encode it to Base64, and update your `.env` or GitHub Secrets.

## 2. Gemini AI Failures
**Symptoms**: `503 Service Unavailable` or `Classification failed`.
- **Cause**: Rate limits or temporary Google AI platform downtime.
- **Fix**: The system has built-in `tenacity` retries. Check the Orchestrator logs to see if it recovers automatically. Ensure your `GEMINI_API_KEY` is valid.

## 3. Worker Not Claiming Tasks
**Symptoms**: Tasks stay in "Pending" status in the `pipeline_tasks` table.
- **Cause**: The background worker thread crashed or the Orchestrator isn't running.
- **Fix**:
  - Restart the Orchestrator service.
  - Check `orchestrator.stderr.log` for Python tracebacks.
  - Verify the `claim_next_task` RPC exists in Supabase.

## 4. Duplicate Applications
**Symptoms**: Same job appearing twice in the dashboard.
- **Cause**: Fuzzy matching threshold might be too high, or `thread_id` changed.
- **Fix**: Adjust the fuzzy matching parameters in `apps/tracker/supabase_service.py` or manually merge applications via the SQL console.

## 5. Dashboard Logs Empty
**Symptoms**: "No logs found" on the Pipeline page during a run.
- **Cause**: Real-time log sinking failed due to Supabase rate limits or incorrect `run_id` mapping.
- **Fix**: Check `tracker.log` on the server for the local copy of the logs.
