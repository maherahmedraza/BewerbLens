-- ╔══════════════════════════════════════════════════════════════╗
-- ║  SQL Schema for Supabase — BewerbLens                       ║
-- ║  Run this script in the Supabase SQL Editor.                ║
-- ║                                                             ║
-- ║  The UNIQUE constraint on thread_id eliminates the          ║
-- ║  deduplication problem that the n8n workflow solved with JS.║
-- ╚══════════════════════════════════════════════════════════════╝

-- ── Main applications table ───────────────────────────────────
-- Equivalent to the "Applications" Google Sheet
CREATE TABLE IF NOT EXISTS applications (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    thread_id       TEXT UNIQUE NOT NULL,  -- Guarantees zero duplicates per email thread
    company_name    TEXT NOT NULL,
    job_title       TEXT DEFAULT 'Not Specified',
    platform        TEXT DEFAULT 'Direct',
    status          TEXT NOT NULL,
    confidence      FLOAT DEFAULT 0.0,
    email_subject   TEXT DEFAULT '',
    email_from      TEXT DEFAULT '',
    date_applied    DATE DEFAULT CURRENT_DATE,
    last_updated    TIMESTAMPTZ DEFAULT timezone('utc', now()),
    notes           TEXT DEFAULT '',
    processed_at    TIMESTAMPTZ DEFAULT timezone('utc', now())
);

-- Index for fast deduplication queries
CREATE INDEX IF NOT EXISTS idx_applications_thread_id ON applications(thread_id);

-- Index for status queries (dashboard queries)
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);

-- Index for incremental checkpoint (get last processed)
CREATE INDEX IF NOT EXISTS idx_applications_processed_at ON applications(processed_at DESC);

-- ── AI processing logs table ──────────────────────────────────
-- Equivalent to the "Classification Log" Google Sheet
CREATE TABLE IF NOT EXISTS ai_processing_logs (
    id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    thread_id               TEXT DEFAULT '',
    email_subject           TEXT DEFAULT '',
    classification_result   TEXT DEFAULT '',
    error_message           TEXT DEFAULT '',
    processed_at            TIMESTAMPTZ DEFAULT timezone('utc', now())
);

-- Index for temporal debugging
CREATE INDEX IF NOT EXISTS idx_logs_processed_at ON ai_processing_logs(processed_at DESC);

-- ── View for the dashboard ────────────────────────────────────
-- Equivalent to the "Dashboard" Google Sheet
CREATE OR REPLACE VIEW application_stats AS
SELECT
    COUNT(*)                                        AS total_applications,
    COUNT(*) FILTER (WHERE status = 'Applied')      AS applied,
    COUNT(*) FILTER (WHERE status = 'Rejected')     AS rejected,
    COUNT(*) FILTER (WHERE status = 'Positive Response') AS positive_response,
    COUNT(*) FILTER (WHERE status = 'Interview')    AS interview,
    COUNT(*) FILTER (WHERE status = 'Offer')        AS offer,
    ROUND(
        COUNT(*) FILTER (WHERE status IN ('Rejected', 'Positive Response', 'Interview', 'Offer'))::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 1
    ) AS response_rate_pct,
    ROUND(
        COUNT(*) FILTER (WHERE status IN ('Positive Response', 'Interview', 'Offer'))::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 1
    ) AS success_rate_pct
FROM applications;

-- ── View by platform ──────────────────────────────────────────
CREATE OR REPLACE VIEW platform_breakdown AS
SELECT
    platform,
    COUNT(*) AS count,
    COUNT(*) FILTER (WHERE status = 'Rejected') AS rejected,
    COUNT(*) FILTER (WHERE status IN ('Positive Response', 'Interview', 'Offer')) AS positive
FROM applications
GROUP BY platform
ORDER BY count DESC;
