-- ╔══════════════════════════════════════════════════════════════╗
-- ║  Migration 0007 — Status History for Thread View           ║
-- ║  Adds a chronologically ordered array of status updates.    ║
-- ╚══════════════════════════════════════════════════════════════╝

-- 1. Add status_history column if it doesn't exist
ALTER TABLE applications 
  ADD COLUMN IF NOT EXISTS status_history JSONB DEFAULT '[]'::jsonb;

-- 2. Backfill existing data
-- Creates an initial entry for each application based on current status and date_applied.
UPDATE applications
SET status_history = jsonb_build_array(
  jsonb_build_object(
    'status', status,
    'date', date_applied::text,
    'source', 'migration_v2',
    'changed_at', last_updated::text,
    'email_subject', email_subject
  )
)
WHERE status_history = '[]'::jsonb OR status_history IS NULL;

-- 3. Add index for JSONB queries
CREATE INDEX IF NOT EXISTS idx_applications_status_history ON applications USING GIN (status_history);

COMMENT ON COLUMN applications.status_history IS 'Array of {"status": string, "date": string, "changed_at": timestamp, "email_subject": string}';
