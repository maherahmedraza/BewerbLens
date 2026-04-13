-- ╔══════════════════════════════════════════════════════════════╗
-- ║  BewerbLens v3.0 Schema Migration                           ║
-- ║                                                             ║
-- ║  Implements enterprise-grade features:                      ║
-- ║  • Proper application threading (status_history)            ║
-- ║  • Efficient log storage with partitioning                  ║
-- ║  • Zombie detection via heartbeats                          ║
-- ║  • Retry tracking and failure analytics                     ║
-- ╚══════════════════════════════════════════════════════════════╝

-- ══════════════════════════════════════════════════════════════
-- MIGRATION 1: Enhance Applications Table for Threading
-- ══════════════════════════════════════════════════════════════

-- Add new columns if they don't exist
DO $$
BEGIN
    -- status_history: Array of all status transitions
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'applications' AND column_name = 'status_history'
    ) THEN
        ALTER TABLE applications ADD COLUMN status_history JSONB DEFAULT '[]'::jsonb;
    END IF;

    -- email_count: Number of emails in this thread
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'applications' AND column_name = 'email_count'
    ) THEN
        ALTER TABLE applications ADD COLUMN email_count INTEGER DEFAULT 1;
    END IF;

    -- is_active: Soft delete flag
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'applications' AND column_name = 'is_active'
    ) THEN
        ALTER TABLE applications ADD COLUMN is_active BOOLEAN DEFAULT true;
    END IF;
END
$$;

-- Create optimized indexes for fuzzy matching
CREATE INDEX IF NOT EXISTS idx_applications_fuzzy_company_job 
ON applications(company_name, job_title) 
WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_applications_thread_active 
ON applications(thread_id) 
WHERE is_active = true;

-- ══════════════════════════════════════════════════════════════
-- MIGRATION 2: Backfill status_history for Existing Data
-- ══════════════════════════════════════════════════════════════

-- Convert existing applications to have initial status_history entry
UPDATE applications
SET status_history = jsonb_build_array(
    jsonb_build_object(
        'timestamp', date_applied::text,
        'status', status,
        'email_subject', email_subject,
        'source_email_id', source_email_id,
        'confidence', confidence
    )
)
WHERE status_history = '[]'::jsonb OR status_history IS NULL;

-- ══════════════════════════════════════════════════════════════
-- MIGRATION 3: Enhanced Pipeline Runs Table
-- ══════════════════════════════════════════════════════════════

-- Add retry tracking
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'pipeline_runs' AND column_name = 'retry_count'
    ) THEN
        ALTER TABLE pipeline_runs ADD COLUMN retry_count INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'pipeline_runs' AND column_name = 'is_zombie'
    ) THEN
        ALTER TABLE pipeline_runs ADD COLUMN is_zombie BOOLEAN DEFAULT false;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'pipeline_runs' AND column_name = 'partial_success'
    ) THEN
        ALTER TABLE pipeline_runs ADD COLUMN partial_success BOOLEAN DEFAULT false;
    END IF;
END
$$;

-- Index for zombie detection queries
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_zombie_detection 
ON pipeline_runs(status, heartbeat_at) 
WHERE status = 'running';

-- ══════════════════════════════════════════════════════════════
-- MIGRATION 4: Log Partitioning for Performance
-- ══════════════════════════════════════════════════════════════

-- Create partitioned logs table for high-volume logging
-- (Only if you expect 100k+ logs per month - otherwise skip)

/*
CREATE TABLE pipeline_run_logs_partitioned (
    id bigint GENERATED ALWAYS AS IDENTITY,
    run_id uuid NOT NULL,
    step_name text,
    level text NOT NULL,
    message text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE pipeline_run_logs_2026_04 PARTITION OF pipeline_run_logs_partitioned
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE TABLE pipeline_run_logs_2026_05 PARTITION OF pipeline_run_logs_partitioned
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- Index on each partition
CREATE INDEX idx_logs_2026_04_run_id ON pipeline_run_logs_2026_04(run_id);
CREATE INDEX idx_logs_2026_05_run_id ON pipeline_run_logs_2026_05(run_id);
*/

-- ══════════════════════════════════════════════════════════════
-- MIGRATION 5: Helper Functions
-- ══════════════════════════════════════════════════════════════

-- Function: Get unique application count (excludes soft-deleted)
CREATE OR REPLACE FUNCTION count_unique_applications()
RETURNS INTEGER AS $$
    SELECT COUNT(*)::INTEGER 
    FROM applications 
    WHERE is_active = true;
$$ LANGUAGE SQL STABLE;

-- Function: Get total emails tracked
CREATE OR REPLACE FUNCTION count_total_emails()
RETURNS INTEGER AS $$
    SELECT COALESCE(SUM(email_count), 0)::INTEGER 
    FROM applications 
    WHERE is_active = true;
$$ LANGUAGE SQL STABLE;

-- Function: Detect zombie runs
CREATE OR REPLACE FUNCTION detect_zombie_runs(threshold_minutes INTEGER DEFAULT 10)
RETURNS TABLE(run_id uuid, run_identifier text, last_heartbeat timestamptz) AS $$
    SELECT 
        id as run_id,
        run_id as run_identifier,
        heartbeat_at as last_heartbeat
    FROM pipeline_runs
    WHERE 
        status = 'running' 
        AND heartbeat_at < NOW() - (threshold_minutes || ' minutes')::INTERVAL
        AND is_zombie = false;
$$ LANGUAGE SQL STABLE;

-- Function: Kill a zombie run
CREATE OR REPLACE FUNCTION kill_zombie_run(target_run_id uuid)
RETURNS void AS $$
    UPDATE pipeline_runs
    SET 
        status = 'failed',
        is_zombie = true,
        error_message = 'Pipeline zombie-killed: No heartbeat for 10+ minutes',
        ended_at = NOW()
    WHERE id = target_run_id;
$$ LANGUAGE SQL;

-- ══════════════════════════════════════════════════════════════
-- MIGRATION 6: Updated Analytics Views
-- ══════════════════════════════════════════════════════════════

-- Drop old views
DROP VIEW IF EXISTS application_stats CASCADE;

-- Create updated stats view (uses is_active filter)
CREATE OR REPLACE VIEW application_stats AS
SELECT
    count_unique_applications() AS total_applications,
    count_total_emails() AS total_emails,
    COUNT(*) FILTER (WHERE status = 'Applied' AND is_active = true) AS applied,
    COUNT(*) FILTER (WHERE status = 'Rejected' AND is_active = true) AS rejected,
    COUNT(*) FILTER (WHERE status = 'Positive Response' AND is_active = true) AS positive_response,
    COUNT(*) FILTER (WHERE status = 'Interview' AND is_active = true) AS interview,
    COUNT(*) FILTER (WHERE status = 'Offer' AND is_active = true) AS offer,
    ROUND(
        COUNT(*) FILTER (WHERE status IN ('Rejected', 'Positive Response', 'Interview', 'Offer') AND is_active = true)::NUMERIC
        / NULLIF(count_unique_applications(), 0) * 100, 1
    ) AS response_rate_pct,
    ROUND(
        COUNT(*) FILTER (WHERE status IN ('Positive Response', 'Interview', 'Offer') AND is_active = true)::NUMERIC
        / NULLIF(count_unique_applications(), 0) * 100, 1
    ) AS success_rate_pct
FROM applications;

-- ══════════════════════════════════════════════════════════════
-- MIGRATION 7: Performance Optimization
-- ══════════════════════════════════════════════════════════════

-- Add GIN index for JSONB searching in status_history
CREATE INDEX IF NOT EXISTS idx_applications_status_history_gin 
ON applications USING GIN (status_history);

-- Add composite index for common dashboard query
CREATE INDEX IF NOT EXISTS idx_applications_dashboard 
ON applications(status, last_updated DESC) 
WHERE is_active = true;

-- Add index for run logs retrieval
CREATE INDEX IF NOT EXISTS idx_pipeline_run_logs_run_created 
ON pipeline_run_logs(run_id, created_at DESC);

-- ══════════════════════════════════════════════════════════════
-- MIGRATION 8: Scheduled Cleanup Jobs (Optional)
-- ══════════════════════════════════════════════════════════════

-- Auto-delete old logs (keep last 90 days only)
CREATE OR REPLACE FUNCTION cleanup_old_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM pipeline_run_logs
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Auto-archive completed runs older than 30 days
CREATE TABLE IF NOT EXISTS pipeline_runs_archive (
    LIKE pipeline_runs INCLUDING ALL
);

CREATE OR REPLACE FUNCTION archive_old_runs()
RETURNS INTEGER AS $$
DECLARE
    archived_count INTEGER;
BEGIN
    -- Move to archive
    INSERT INTO pipeline_runs_archive
    SELECT * FROM pipeline_runs
    WHERE 
        status IN ('success', 'failed')
        AND ended_at < NOW() - INTERVAL '30 days';
    
    GET DIAGNOSTICS archived_count = ROW_COUNT;
    
    -- Delete from main table
    DELETE FROM pipeline_runs
    WHERE 
        status IN ('success', 'failed')
        AND ended_at < NOW() - INTERVAL '30 days';
    
    RETURN archived_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ══════════════════════════════════════════════════════════════
-- MIGRATION COMPLETE
-- ══════════════════════════════════════════════════════════════

-- Verify migration success
SELECT 
    'Migration Complete!' as status,
    count_unique_applications() as unique_apps,
    count_total_emails() as total_emails,
    (SELECT COUNT(*) FROM pipeline_run_logs) as total_logs;