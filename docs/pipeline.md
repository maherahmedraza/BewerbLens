# Pipeline Guide

BewerbLens processes job application emails through a three-stage modular pipeline. Each stage is independently executable, and failed stages can be re-run without repeating earlier work.

---

## Stages

### 1. Ingestion (`ingestion`)
Fetches new emails from Gmail and stores them in the `raw_emails` table.

- Connects via OAuth2 using per-user credentials from `user_profiles.gmail_credentials`
- Only fetches emails since the last successful checkpoint (`get_last_checkpoint`)
- Recovers any previously unprocessed emails (`is_processed = false`)
- Applies per-user email filter rules from the `email_filters` table
- Persists stage output (email IDs, counts) in `pipeline_run_steps.stats`

### 2. Analysis (`analysis`)
Classifies emails using Gemini AI.

- Loads email IDs from Ingestion's persisted stats (not from memory)
- Fetches raw email bodies from `raw_emails`
- Sends batch classification requests to Gemini 3.1 Flash-Lite
- Uses Structured Outputs (JSON Schema) for robust parsing
- Each email is classified as: `application_confirmation`, `rejection`, `positive_response`, or `not_job_related`
- Persists classifications in `pipeline_run_steps.stats`

### 3. Persistence (`persistence`)
Upserts classified applications into the `applications` table.

- Loads both Ingestion and Analysis stage artifacts from `pipeline_run_steps.stats`
- Uses `ApplicationMatcher` (fuzzy matching) to detect existing applications
- Matching key: `(company_name, job_title)` — same company + different job = separate applications
- Status Priority: terminal states (Offer=100, Rejected=99) cannot be downgraded
- Sends Telegram notifications for new/updated applications

---

## Running the Pipeline

### From the Dashboard

1. Go to the **Pipeline** page
2. Click **Manual Sync** to start a full run
3. Monitor progress in real-time via the stage progress bars
4. View logs by clicking **View Logs** on the monitor or the info icon in Execution History

### Re-running a Failed Stage

When a stage fails:
1. The pipeline halts — downstream stages do not execute
2. The failed stage shows an error message and a **"Rerun from [Stage]"** button
3. Click the button to reset that stage and all downstream stages, then re-execute
4. Previous stages' outputs are loaded from persisted artifacts (not re-executed)

### Via the API

```bash
# Trigger a full run
curl -X POST http://localhost:8000/runs/trigger \
  -H "Content-Type: application/json" \
  -d '{"user_id": "your-uuid", "triggered_by": "manual"}'

# Resume a failed run from the first incomplete stage
curl -X POST http://localhost:8000/runs/{run_id}/resume

# Rerun from a specific stage (resets downstream stages)
curl -X POST http://localhost:8000/runs/{run_id}/rerun-stage \
  -H "Content-Type: application/json" \
  -d '{"stage": "analysis"}'

# Cancel an active run
curl -X POST http://localhost:8000/runs/{run_id}/cancel
```

---

## Stage Artifact Persistence

Each stage saves its output to `pipeline_run_steps.stats` (JSONB). This enables:

- **Resume**: If the worker crashes mid-pipeline, a new worker can pick up from the failed stage using persisted artifacts from completed stages
- **Stage Rerun**: Resetting a stage clears its stats and all downstream stats, then re-executes from that point
- **Debugging**: Stage stats are queryable — inspect what emails were fetched, how they were classified, etc.

| Stage | Stats Model | Key Fields |
|-------|-------------|------------|
| Ingestion | `IngestionStageStats` | `email_ids`, `total_fetched`, `total_recovered`, `total_after_filters` |
| Analysis | `AnalysisStageStats` | `email_ids`, `classifications`, `total_classified` |
| Persistence | `PersistenceStageStats` | `email_ids`, `added`, `updated`, `skipped`, `errors` |

---

## Cancellation

Cancellation is **cooperative**: the worker checks `pipeline_runs.status` periodically (throttled to every 5 seconds). When a cancel is requested:

1. If the task hasn't been claimed yet → task is marked `failed`, run is marked `cancelled`
2. If the task is actively running → run status is set to `cancelling`, worker detects this on the next check and raises `PipelineCancelledError`

---

## Configuration

Pipeline config is stored in the `pipeline_config` table (singleton row):

| Setting | Default | Description |
|---------|---------|-------------|
| `schedule_interval_hours` | 4.0 | Hours between automatic runs |
| `is_paused` | false | Pauses the scheduler without stopping the server |
| `retention_days` | 30 | Days to keep historical run data |

Update via the dashboard Config Panel or the `/config/` API endpoint.
