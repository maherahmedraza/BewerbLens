-- ╔══════════════════════════════════════════════════════════════╗
-- ║  Sprint 3 Hotfix — Expand application_stats view            ║
-- ║                                                             ║
-- ║  Dashboard pages reference individual status fields:        ║
-- ║  positive_response, interview, offer — but the view only   ║
-- ║  had an aggregated "positive" column. Fix the view.         ║
-- ╚══════════════════════════════════════════════════════════════╝

DROP VIEW IF EXISTS application_stats CASCADE;

CREATE OR REPLACE VIEW application_stats AS
SELECT
    user_id,
    COUNT(*) FILTER (WHERE is_active = true) AS total_applications,
    SUM(email_count) FILTER (WHERE is_active = true) AS total_emails,
    COUNT(*) FILTER (WHERE status = 'Applied' AND is_active = true) AS applied,
    COUNT(*) FILTER (WHERE status = 'Rejected' AND is_active = true) AS rejected,
    COUNT(*) FILTER (WHERE status = 'Positive Response' AND is_active = true) AS positive_response,
    COUNT(*) FILTER (WHERE status = 'Interview' AND is_active = true) AS interview,
    COUNT(*) FILTER (WHERE status = 'Offer' AND is_active = true) AS offer,
    COUNT(*) FILTER (WHERE status IN ('Positive Response', 'Interview', 'Offer') AND is_active = true) AS positive,
    ROUND(
        COUNT(*) FILTER (WHERE status != 'Applied' AND is_active = true)::NUMERIC
        / NULLIF(COUNT(*) FILTER (WHERE is_active = true), 0) * 100, 1
    ) AS response_rate_pct,
    ROUND(
        COUNT(*) FILTER (WHERE status IN ('Positive Response', 'Interview', 'Offer') AND is_active = true)::NUMERIC
        / NULLIF(COUNT(*) FILTER (WHERE is_active = true), 0) * 100, 1
    ) AS success_rate_pct
FROM applications
GROUP BY user_id;

ALTER VIEW application_stats SET (security_invoker = true);
