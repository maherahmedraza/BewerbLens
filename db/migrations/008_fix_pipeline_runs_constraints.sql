-- Migration 008: Fix pipeline_runs check constraints for rerun/resume support
--
-- Problem: The triggered_by CHECK only allows 'manual' and 'scheduler',
-- but the modular pipeline now sends 'rerun:ingestion', 'rerun:analysis',
-- 'rerun:persistence', and 'resume'.
--
-- Problem: The duration_check constraint blocks zombie cleanup when
-- marking abandoned runs as failed (sets ended_at but duration_ms may be null).

-- 1. Drop and recreate triggered_by constraint to allow rerun/resume values
DO $$
BEGIN
    ALTER TABLE pipeline_runs DROP CONSTRAINT IF EXISTS pipeline_runs_triggered_by_check;
    RAISE NOTICE 'Dropped old triggered_by check constraint';
EXCEPTION
    WHEN undefined_object THEN
        RAISE NOTICE 'triggered_by check constraint did not exist';
END $$;

-- Allow: manual, scheduler, rerun:ingestion, rerun:analysis, rerun:persistence, resume
ALTER TABLE pipeline_runs
    ADD CONSTRAINT pipeline_runs_triggered_by_check
    CHECK (triggered_by IN (
        'manual', 'scheduler',
        'rerun:ingestion', 'rerun:analysis', 'rerun:persistence',
        'resume'
    ));

-- 2. Fix duration_check: allow ended_at without duration_ms (for zombie cleanup)
DO $$
BEGIN
    ALTER TABLE pipeline_runs DROP CONSTRAINT IF EXISTS duration_check;
    RAISE NOTICE 'Dropped old duration_check constraint';
EXCEPTION
    WHEN undefined_object THEN
        RAISE NOTICE 'duration_check constraint did not exist';
END $$;

-- duration_ms is optional; only validate that it's non-negative when present
ALTER TABLE pipeline_runs
    ADD CONSTRAINT duration_check
    CHECK (duration_ms IS NULL OR duration_ms >= 0);

-- 3. Fix any zombie runs that were stuck due to the old constraint
UPDATE pipeline_runs
SET status = 'failed',
    error_message = COALESCE(error_message, 'Pipeline zombie-killed: recovered by migration 008'),
    ended_at = COALESCE(ended_at, now())
WHERE status = 'running'
  AND last_heartbeat < now() - interval '30 minutes';
