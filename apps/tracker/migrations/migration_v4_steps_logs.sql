-- ╔══════════════════════════════════════════════════════════════╗
-- ║  BewerbLens Migration v4 — Durable Orchestration             ║
-- ║  Adds Steps, Logs, and Run Hardening.                        ║
-- ╚══════════════════════════════════════════════════════════════╝

-- ── 1. Pipeline Run Steps ──────────────────────────
-- Explicitly track progress for each stage of the pipeline.
-- This enables Airflow-style pulse indicators in the UI.
CREATE TABLE IF NOT EXISTS pipeline_run_steps (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id            UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step_name         TEXT NOT NULL CHECK (step_name IN ('ingestion', 'analysis', 'persistence')),
    status            TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'success', 'failed', 'skipped')),
    progress_pct      INT NOT NULL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
    message           TEXT DEFAULT '',
    started_at        TIMESTAMPTZ,
    ended_at          TIMESTAMPTZ,
    stats             JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (run_id, step_name)
);

CREATE INDEX IF NOT EXISTS idx_run_steps_run_id ON pipeline_run_steps(run_id);

-- ── 2. Pipeline Run Incremental Logs ────────────────
-- Persist logs row-by-row during execution.
-- This enables live-tailing in the dashboard drawer.
CREATE TABLE IF NOT EXISTS pipeline_run_logs (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id            UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step_name         TEXT,
    level             TEXT NOT NULL,
    message           TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_run_logs_run_id ON pipeline_run_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_run_logs_created ON pipeline_run_logs(created_at);

-- ── 3. Hardening Pipeline Runs ──────────────────────
-- Track worker health and task associations.
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS task_id UUID REFERENCES pipeline_tasks(id);

-- Optional: If current_phase is no longer needed after migration, we keep it for backward compat for now.

-- ── 4. Verify Task Table ─────────────────────────────
-- Ensure pipeline_tasks has the latest status constraints.
-- (Assumes pipeline_tasks already exists from v3).
-- ALTER TABLE pipeline_tasks DROP CONSTRAINT IF EXISTS pipeline_tasks_status_check;
-- ALTER TABLE pipeline_tasks ADD CONSTRAINT pipeline_tasks_status_check CHECK (status IN ('pending', 'claimed', 'running', 'done', 'failed', 'cancelled'));
