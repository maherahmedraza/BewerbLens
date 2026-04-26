-- Migration 013: Pipeline controls and follow-up reminder tracking
--
-- Adds:
-- 1. max_emails_per_run on pipeline_config to cap large backfills per run
-- 2. last_follow_up_reminder_at on applications to avoid daily reminder spam

ALTER TABLE pipeline_config
ADD COLUMN IF NOT EXISTS max_emails_per_run integer;

UPDATE pipeline_config
SET max_emails_per_run = COALESCE(max_emails_per_run, 250);

ALTER TABLE pipeline_config
ALTER COLUMN max_emails_per_run SET DEFAULT 250;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'pipeline_config_max_emails_per_run_check'
  ) THEN
    ALTER TABLE pipeline_config
    ADD CONSTRAINT pipeline_config_max_emails_per_run_check
    CHECK (max_emails_per_run BETWEEN 25 AND 5000);
  END IF;
END $$;

ALTER TABLE applications
ADD COLUMN IF NOT EXISTS last_follow_up_reminder_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_applications_follow_up_due
ON applications (user_id, status, date_applied, last_follow_up_reminder_at);
