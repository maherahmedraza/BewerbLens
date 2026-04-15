# Orchestrator API Documentation

The Orchestrator provides a REST API to manage pipeline executions and configuration.

**Base URL**: `http://localhost:8000` (Default)

---

## ── Runs Management (`/runs`)

### Trigger a Run
Manually triggers a new pipeline execution.

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
- **Response** (200 OK):
  ```json
  {
    "run_id": "RUN-LABEL-123",
    "id": "uuid-of-run",
    "status": "running"
  }
  ```

### Execution History
Fetches a paginated list of previous runs.

- **URL**: `/runs/history`
- **Method**: `GET`
- **Parameters**: `limit` (int), `offset` (int)
- **Response**: Array of run objects including timestamps and summary stats.

### Run Details
Retrieves detailed metadata for a specific run.

- **URL**: `/runs/{run_id}`
- **Method**: `GET`
- **Response**: Full run object including `logs_summary` and `summary_stats`.

---

## ── Configuration (`/config`)

### Get Global Config
Retrieves the current pipeline settings (retention, schedule, etc.).

- **URL**: `/config/`
- **Method**: `GET`

### Update Config
Updates specific configuration fields.

- **URL**: `/config/`
- **Method**: `PATCH`
- **Payload**:
  ```json
  {
    "is_paused": false,
    "sync_interval_minutes": 60,
    "retention_days": 30
  }
  ```

---

## ── Health Check

### System Status
Verifies if the API, Worker, and Scheduler are active.

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
