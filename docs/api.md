# Orchestrator API Documentation

The Orchestrator provides a REST API to manage pipeline executions and configuration.

**Base URL**: `http://localhost:8000` (default).  
Set `NEXT_PUBLIC_ORCHESTRATOR_URL` in the dashboard's environment to override.

---

## ── Runs Management (`/runs`)

### Trigger a Run
Manually triggers a new pipeline execution. The endpoint returns immediately; execution continues asynchronously in the background worker.

- **URL**: `/runs/trigger`
- **Method**: `POST`
- **Payload**:
  ```json
  {
    "user_id": "uuid-string",
    "since_date": "2024-01-01",
    "triggered_by": "manual"
  }
  ```
  - `triggered_by` must be `"manual"` or `"backfill"`. The scheduler uses an internal code path and does not call this endpoint.
  - `since_date` is optional; defaults to the last checkpoint stored in Supabase.
- **Response** (200 OK):
  ```json
  {
    "run_id": "RUN-20240601-120000-abc123",
    "id": "uuid-of-pipeline-run",
    "status": "running",
    "current_phase": "ingestion"
  }
  ```
  - `run_id`: Human-readable label (e.g. `RUN-YYYYMMDD-HHMMSS-xxxxxx`).
  - `id`: UUID of the `pipeline_runs` row; use this to query step progress from `pipeline_run_steps`.

### Execution History
Fetches a paginated list of previous runs, ordered newest-first.

- **URL**: `/runs/history`
- **Method**: `GET`
- **Query parameters**: `limit` (int, default 20), `offset` (int, default 0)
- **Response**: Array of `pipeline_runs` rows including `status`, `started_at`, `duration_ms`, `summary_stats`, and `error_message`.

### Run Details
Retrieves full metadata for a specific run. Accepts either the human-readable `run_id` label or the UUID `id`.

- **URL**: `/runs/{run_id}`
- **Method**: `GET`
- **Response**: Single `pipeline_runs` row. Returns `404` if not found.

### Cancel a Run
Requests cooperative cancellation for a pending or active run.

- **URL**: `/runs/{run_id}/cancel`
- **Method**: `POST`
- **Response** (200 OK):
  ```json
  {
    "run_id": "RUN-20240601-120000-abc123",
    "id": "uuid-of-pipeline-run",
    "status": "cancelling"
  }
  ```

### Resume a Run
Resumes a failed or cancelled run from the first incomplete stage.

- **URL**: `/runs/{run_id}/resume`
- **Method**: `POST`
- **Response** (200 OK):
  ```json
  {
    "run_id": "RUN-20240601-120000-abc123",
    "id": "uuid-of-pipeline-run",
    "status": "running",
    "current_phase": "analysis"
  }
  ```

### Rerun a Specific Stage
Resets the selected stage and all downstream stages, then requeues the run from that point.

- **URL**: `/runs/{run_id}/rerun-stage`
- **Method**: `POST`
- **Payload**:
  ```json
  {
    "stage": "analysis"
  }
  ```
- **Allowed values**: `ingestion`, `analysis`, `persistence`
- **Response** (200 OK):
  ```json
  {
    "run_id": "RUN-20240601-120000-abc123",
    "id": "uuid-of-pipeline-run",
    "status": "running",
    "current_phase": "analysis"
  }
  ```

---

## ── Configuration (`/config`)

The global pipeline configuration is stored as a singleton row in the `pipeline_config` table. All fields are optional in a PATCH request — only supplied fields are updated.

### Get Current Config

- **URL**: `/config/`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "id": "00000000-0000-0000-0000-000000000001",
    "schedule_interval_hours": 4.0,
    "retention_days": 30,
    "is_paused": false
  }
  ```

### Update Config

- **URL**: `/config/`
- **Method**: `PATCH`
- **Payload** (all fields optional):
  ```json
  {
    "is_paused": false,
    "schedule_interval_hours": 4.0,
    "retention_days": 30
  }
  ```
  - `is_paused: true` removes the scheduled job from APScheduler without stopping the server.
  - `schedule_interval_hours` accepts a float (e.g. `1.0`, `4.0`, `12.0`, `24.0`). The scheduler reschedules itself dynamically — no restart required.
- **Response**: Updated config object.
- **Error** (400): Returned when the request body contains no recognised fields.

---

## ── Health Check

### System Status
Verifies if the API, worker thread, and scheduler are active.

- **URL**: `/health`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "status": "ok",
    "worker": "active",
    "scheduler": true
  }
  ```
  - `scheduler` is `false` when the pipeline is paused or the scheduler failed to start.
