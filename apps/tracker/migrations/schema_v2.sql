-- ╔══════════════════════════════════════════════════════════════╗
-- ║  Schema V2 Migration — Medallion Architecture               ║
-- ║  Run this script in the Supabase SQL Editor.                ║
-- ║                                                             ║
-- ║  WARNING: This drops and recreates existing tables.         ║
-- ║  Your application data will be preserved in a backup table.  ║
-- ╚══════════════════════════════════════════════════════════════╝

-- ── Backup existing data ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS applications_backup AS SELECT * FROM applications;
CREATE TABLE IF NOT EXISTS ai_processing_logs_backup AS SELECT * FROM ai_processing_logs;

-- ── Drop existing tables and views ───────────────────────────
DROP VIEW IF EXISTS conversion_funnel CASCADE;
DROP VIEW IF EXISTS location_breakdown CASCADE;
DROP VIEW IF EXISTS top_companies CASCADE;
DROP VIEW IF EXISTS platform_breakdown CASCADE;
DROP VIEW IF EXISTS monthly_applications CASCADE;
DROP VIEW IF EXISTS application_stats CASCADE;

DROP TABLE IF EXISTS raw_emails CASCADE;
DROP TABLE IF EXISTS applications CASCADE;
DROP TABLE IF EXISTS ai_processing_logs CASCADE;

-- ── Bronze Layer: Raw email storage (NEW) ────────────────────
CREATE TABLE raw_emails (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email_id        TEXT UNIQUE NOT NULL,
    thread_id       TEXT NOT NULL,
    subject         TEXT DEFAULT '',
    sender          TEXT DEFAULT '',
    sender_email    TEXT DEFAULT '',
    body_preview    TEXT DEFAULT '',       -- First 800 chars only (GDPR data minimization)
    email_date      DATE DEFAULT CURRENT_DATE,
    gmail_link      TEXT DEFAULT '',       -- https://mail.google.com/mail/u/0/#inbox/{email_id}
    raw_headers     JSONB DEFAULT '{}',    -- Full headers for debugging
    ingested_at     TIMESTAMPTZ DEFAULT timezone('utc', now()),
    is_processed    BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_raw_emails_email_id ON raw_emails(email_id);
CREATE INDEX idx_raw_emails_thread_id ON raw_emails(thread_id);
CREATE INDEX idx_raw_emails_ingested_at ON raw_emails(ingested_at DESC);

-- ── Silver Layer: Applications (recreated with v2.0 columns) ─
CREATE TABLE applications (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    thread_id       TEXT NOT NULL,
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
    processed_at    TIMESTAMPTZ DEFAULT timezone('utc', now()),
    -- v2.0 new fields
    gmail_link      TEXT DEFAULT '',
    job_listing_url TEXT DEFAULT '',
    location        TEXT DEFAULT '',
    salary_range    TEXT DEFAULT '',
    source_email_id TEXT DEFAULT ''
);

-- Restore data from backup (only columns that exist in both)
INSERT INTO applications (
    id, thread_id, company_name, job_title, platform, status,
    confidence, email_subject, email_from, date_applied,
    last_updated, notes, processed_at
)
SELECT
    id, thread_id, company_name, job_title, platform, status,
    confidence, email_subject, email_from, date_applied,
    last_updated, notes, processed_at
FROM applications_backup
ON CONFLICT (id) DO NOTHING;

CREATE UNIQUE INDEX idx_applications_thread_id ON applications(thread_id);
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_processed_at ON applications(processed_at DESC);
CREATE INDEX idx_applications_company ON applications(company_name);
CREATE INDEX idx_applications_date ON applications(date_applied);
CREATE INDEX idx_applications_location ON applications(location) WHERE location != '';

-- ── AI processing logs (recreated) ───────────────────────────
CREATE TABLE ai_processing_logs (
    id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    thread_id               TEXT DEFAULT '',
    email_subject           TEXT DEFAULT '',
    classification_result   TEXT DEFAULT '',
    error_message           TEXT DEFAULT '',
    processed_at            TIMESTAMPTZ DEFAULT timezone('utc', now())
);

-- Restore data from backup
INSERT INTO ai_processing_logs (
    id, thread_id, email_subject, classification_result,
    error_message, processed_at
)
SELECT
    id, thread_id, email_subject, classification_result,
    error_message, processed_at
FROM ai_processing_logs_backup
ON CONFLICT (id) DO NOTHING;

CREATE INDEX idx_logs_processed_at ON ai_processing_logs(processed_at DESC);

-- ── Gold Layer: Pre-computed analytics views ─────────────────

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

CREATE OR REPLACE VIEW monthly_applications AS
SELECT
    DATE_TRUNC('month', date_applied) AS month,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'Applied') AS applied,
    COUNT(*) FILTER (WHERE status = 'Rejected') AS rejected,
    COUNT(*) FILTER (WHERE status IN ('Positive Response','Interview','Offer')) AS positive
FROM applications
GROUP BY DATE_TRUNC('month', date_applied)
ORDER BY month;

CREATE OR REPLACE VIEW platform_breakdown AS
SELECT
    platform,
    COUNT(*) AS count,
    COUNT(*) FILTER (WHERE status = 'Rejected') AS rejected,
    COUNT(*) FILTER (WHERE status IN ('Positive Response', 'Interview', 'Offer')) AS positive
FROM applications
GROUP BY platform
ORDER BY count DESC;

CREATE OR REPLACE VIEW top_companies AS
SELECT
    company_name,
    COUNT(*) AS applications,
    COUNT(*) FILTER (WHERE status = 'Rejected') AS rejected,
    COUNT(*) FILTER (WHERE status IN ('Positive Response','Interview','Offer')) AS positive,
    MIN(date_applied) AS first_applied
FROM applications
GROUP BY company_name
ORDER BY applications DESC;

CREATE OR REPLACE VIEW location_breakdown AS
SELECT
    location,
    COUNT(*) AS count,
    ROUND(COUNT(*)::NUMERIC / NULLIF(SUM(COUNT(*)) OVER (), 0) * 100, 1) AS pct
FROM applications
WHERE location != ''
GROUP BY location
ORDER BY count DESC;

CREATE OR REPLACE VIEW conversion_funnel AS
SELECT 'Applications Submitted' AS stage, COUNT(*) AS count FROM applications
UNION ALL
SELECT 'Awaiting Response', COUNT(*) FROM applications
WHERE status = 'Applied'
UNION ALL
SELECT 'Positive Response', COUNT(*) FROM applications
WHERE status NOT IN ('Applied', 'Rejected')
UNION ALL
SELECT 'Interview', COUNT(*) FROM applications
WHERE status IN ('Interview', 'Offer')
UNION ALL
SELECT 'Offer', COUNT(*) FROM applications
WHERE status = 'Offer';

-- ── GDPR: Auto-delete raw emails after 90 days ───────────────
CREATE OR REPLACE FUNCTION cleanup_old_raw_emails()
RETURNS void AS $$
BEGIN
    DELETE FROM raw_emails
    WHERE ingested_at < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ── GDPR: Right to Erasure function ──────────────────────────
CREATE OR REPLACE FUNCTION delete_all_data()
RETURNS void AS $$
BEGIN
    DELETE FROM ai_processing_logs;
    DELETE FROM applications;
    DELETE FROM raw_emails;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
