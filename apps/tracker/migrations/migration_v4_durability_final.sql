-- ╔══════════════════════════════════════════════════════════════╗
-- ║  BewerbLens Migration v4 — Durable Orchestration (FINAL)     ║
-- ║  Run this to activate Phase 1 Infrastructure.               ║
-- ╚══════════════════════════════════════════════════════════════╝

-- ── 1. Pipeline Tasks (The Queue) ──────────────────
-- Acts as the command channel between API and Worker.
CREATE TABLE IF NOT EXISTS pipeline_tasks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type         TEXT NOT NULL DEFAULT 'sync',
    status            TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'claimed', 'running', 'done', 'failed', 'cancelled')),
    parameters        JSONB DEFAULT '{}'::jsonb,
    run_id            UUID, -- Linked internal_id from pipeline_runs
    last_error        TEXT,
    claimed_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 2. Raw Emails (Bronze Layer) ────────────────────
-- Stores every email metadata to enable email-level dedup.
CREATE TABLE IF NOT EXISTS raw_emails (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email_id          TEXT UNIQUE NOT NULL, -- GMail's MessageID
    thread_id         TEXT NOT NULL,
    subject           TEXT,
    sender            TEXT,
    date_received     TIMESTAMPTZ,
    raw_payload       JSONB,
    processed_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_raw_emails_email_id ON raw_emails(email_id);

-- ── 3. Pipeline Run Steps ──────────────────────────
-- Explicitly track progress for each stage (Ingestion/Analysis/Persistence).
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

-- ── 4. Pipeline Run Incremental Logs ────────────────
-- Row-based logging for live tailing.
CREATE TABLE IF NOT EXISTS pipeline_run_logs (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id            UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step_name         TEXT,
    level             TEXT NOT NULL,
    message           TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 5. Run Hardening ───────────────────────────────
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS task_id UUID REFERENCES pipeline_tasks(id);
