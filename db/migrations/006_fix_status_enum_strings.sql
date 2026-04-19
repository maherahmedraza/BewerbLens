-- ╔══════════════════════════════════════════════════════════════╗
-- ║  Migration 006 — Fix Python 3.11+ str(Enum) status values  ║
-- ║                                                             ║
-- ║  In Python 3.11+, str(Status.APPLIED) returns               ║
-- ║  "Status.APPLIED" instead of "Applied".  This migration     ║
-- ║  normalizes all rows that were persisted with the raw enum  ║
-- ║  repr string so the SQL views count them correctly.         ║
-- ╚══════════════════════════════════════════════════════════════╝

-- Fix status column values
UPDATE applications SET status = 'Applied'           WHERE status = 'Status.APPLIED';
UPDATE applications SET status = 'Rejected'          WHERE status = 'Status.REJECTED';
UPDATE applications SET status = 'Positive Response' WHERE status = 'Status.POSITIVE_RESPONSE';
UPDATE applications SET status = 'Interview'         WHERE status = 'Status.INTERVIEW';
UPDATE applications SET status = 'Offer'             WHERE status = 'Status.OFFER';

-- Also fix classification-style values that may have leaked through
UPDATE applications SET status = 'Applied'           WHERE status = 'application_confirmation';
UPDATE applications SET status = 'Rejected'          WHERE status = 'rejection';
UPDATE applications SET status = 'Positive Response' WHERE status = 'positive_response';

-- Fix status values inside status_history JSONB arrays
-- Each entry has a "status" key that may contain the raw enum repr
UPDATE applications
SET status_history = (
    SELECT jsonb_agg(
        CASE
            WHEN entry->>'status' = 'Status.APPLIED' THEN jsonb_set(entry, '{status}', '"Applied"')
            WHEN entry->>'status' = 'Status.REJECTED' THEN jsonb_set(entry, '{status}', '"Rejected"')
            WHEN entry->>'status' = 'Status.POSITIVE_RESPONSE' THEN jsonb_set(entry, '{status}', '"Positive Response"')
            WHEN entry->>'status' = 'Status.INTERVIEW' THEN jsonb_set(entry, '{status}', '"Interview"')
            WHEN entry->>'status' = 'Status.OFFER' THEN jsonb_set(entry, '{status}', '"Offer"')
            WHEN entry->>'status' = 'application_confirmation' THEN jsonb_set(entry, '{status}', '"Applied"')
            WHEN entry->>'status' = 'rejection' THEN jsonb_set(entry, '{status}', '"Rejected"')
            WHEN entry->>'status' = 'positive_response' THEN jsonb_set(entry, '{status}', '"Positive Response"')
            ELSE entry
        END
    )
    FROM jsonb_array_elements(status_history::jsonb) AS entry
)
WHERE status_history IS NOT NULL
  AND status_history::text ~ 'Status\.|application_confirmation|rejection|positive_response';

-- Deduplicate status_history entries by source_email_id
-- Keeps only the first occurrence of each source_email_id
UPDATE applications
SET status_history = (
    SELECT jsonb_agg(entry)
    FROM (
        SELECT DISTINCT ON (entry->>'source_email_id') entry
        FROM jsonb_array_elements(status_history::jsonb) WITH ORDINALITY AS t(entry, ord)
        ORDER BY entry->>'source_email_id', ord
    ) deduped
),
email_count = (
    SELECT COUNT(DISTINCT entry->>'source_email_id')
    FROM jsonb_array_elements(status_history::jsonb) AS entry
)
WHERE status_history IS NOT NULL
  AND jsonb_array_length(status_history::jsonb) > 1;
