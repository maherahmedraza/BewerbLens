-- ╔══════════════════════════════════════════════════════════════╗
-- ║  BewerbLens Orchestration v3 — Production Schema           ║
-- ║  Includes Run Tracking, Config Singletons, and Auditing.   ║
-- ╚══════════════════════════════════════════════════════════════╝

-- ── 1. Pipeline Runs (History & Logs) ────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id            TEXT NOT NULL UNIQUE,           -- Human-readable e.g. "20260406-2345"
    status            TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed', 'cancelled')),
    triggered_by      TEXT NOT NULL CHECK (triggered_by IN ('scheduler', 'manual', 'backfill')),
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at          TIMESTAMPTZ,
    duration_ms       BIGINT,
    since_date        DATE,                            -- backfill start point if applicable
    parameters        JSONB DEFAULT '{}',              -- snapshot of inputs
    summary_stats     JSONB DEFAULT '{}',              -- {"new": 5, "updated": 2, "errors": 0}
    logs_summary      TEXT DEFAULT '',                 -- aggregate of critical logs
    full_log_url      TEXT DEFAULT '',                 -- pointer to Supabase Storage path
    current_phase     TEXT DEFAULT 'ingestion',        -- 'ingestion' | 'analysis' | 'persistence' | 'completed'
    error_message     TEXT,
    CONSTRAINT duration_check CHECK ((ended_at IS NULL) OR (duration_ms IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status_time ON pipeline_runs(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_since ON pipeline_runs(since_date);

-- ── 2. Global Pipeline Configuration ──────────────────────────
-- Enforced singleton design (exactly one configuration row)
CREATE TABLE IF NOT EXISTS pipeline_config (
    id                     UUID PRIMARY KEY DEFAULT '00000000-0000-0000-0000-000000000001'::uuid,
    retention_days         INT DEFAULT 30 CHECK (retention_days BETWEEN 1 AND 90),
    schedule_interval_hours NUMERIC(5,2) DEFAULT 4.0 CHECK (schedule_interval_hours >= 0.1),
    is_paused              BOOLEAN DEFAULT false,
    last_full_backfill_at  TIMESTAMPTZ,
    updated_at             TIMESTAMPTZ DEFAULT now(),
    updated_by             TEXT DEFAULT 'system',
    CONSTRAINT single_row CHECK (id = '00000000-0000-0000-0000-000000000001'::uuid)
);

-- Initialize default configuration row
INSERT INTO pipeline_config (id, retention_days, schedule_interval_hours)
VALUES ('00000000-0000-0000-0000-000000000001', 30, 4.0)
ON CONFLICT (id) DO NOTHING;

-- ── 3. Configuration Audit Trail ─────────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_config_audit (
    id SERIAL PRIMARY KEY,
    config_id UUID REFERENCES pipeline_config(id) ON DELETE CASCADE,
    changed_at TIMESTAMPTZ DEFAULT now(),
    changed_by TEXT,
    old_values JSONB,
    new_values JSONB
);

-- Trigger to automatically track changes in the audit trail
CREATE OR REPLACE FUNCTION track_config_changes()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO pipeline_config_audit (config_id, changed_by, old_values, new_values)
    VALUES (OLD.id, NEW.updated_by, to_jsonb(OLD), to_jsonb(NEW));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_audit_config ON pipeline_config;
CREATE TRIGGER tr_audit_config
AFTER UPDATE ON pipeline_config
FOR EACH ROW
EXECUTE FUNCTION track_config_changes();

-- ── 4. Manual Task Queue ─────────────────────────────────────
-- Bridge between Next.js UI and the Orchestrator API
CREATE TABLE IF NOT EXISTS pipeline_tasks (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    task_type       TEXT NOT NULL DEFAULT 'sync',
    status          TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'claimed', 'done'
    parameters      JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT timezone('utc', now()),
    claimed_at      TIMESTAMPTZ,
    run_id          UUID REFERENCES pipeline_runs(id)
);
