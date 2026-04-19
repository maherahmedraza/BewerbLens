-- Migration 009: Reset pipeline data for full reprocessing
--
-- Run this AFTER migrations 006, 007, and 008.
-- This resets is_processed on all raw_emails so the pipeline can
-- reprocess everything with the fixed logic.
--
-- WARNING: This will cause the next pipeline run to reprocess ALL emails.
-- It will NOT delete existing applications — the dedup logic in
-- fuzzy_matcher will skip emails already in status_history.

-- Step 1: Reset all raw_emails to unprocessed
UPDATE raw_emails
SET is_processed = false;

-- Step 2: Verify the count
DO $$
DECLARE
    total_count integer;
BEGIN
    SELECT count(*) INTO total_count FROM raw_emails WHERE is_processed = false;
    RAISE NOTICE 'Reset % raw emails to is_processed=false', total_count;
END $$;
