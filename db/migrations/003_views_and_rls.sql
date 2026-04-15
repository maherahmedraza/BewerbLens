-- ╔══════════════════════════════════════════════════════════════╗
-- ║  Sprint 2 Migration — Views, RLS, Status Alignment          ║
-- ║                                                             ║
-- ║  T-002: Update 5 stale views for multi-user                 ║
-- ║  T-003: Add missing RLS on pipeline_tasks, pipeline_run_steps║
-- ╚══════════════════════════════════════════════════════════════╝

-- ══════════════════════════════════════════════════════════════
-- T-002: UPDATE 5 STALE VIEWS — Add user_id grouping
-- ══════════════════════════════════════════════════════════════

-- 1. monthly_applications
DROP VIEW IF EXISTS monthly_applications CASCADE;
CREATE OR REPLACE VIEW monthly_applications AS
SELECT
    user_id,
    DATE_TRUNC('month', date_applied) AS month,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'Applied') AS applied,
    COUNT(*) FILTER (WHERE status = 'Rejected') AS rejected,
    COUNT(*) FILTER (WHERE status IN ('Positive Response','Interview','Offer')) AS positive
FROM applications
WHERE is_active = true
GROUP BY user_id, DATE_TRUNC('month', date_applied)
ORDER BY month;

ALTER VIEW monthly_applications SET (security_invoker = true);

-- 2. platform_breakdown
DROP VIEW IF EXISTS platform_breakdown CASCADE;
CREATE OR REPLACE VIEW platform_breakdown AS
SELECT
    user_id,
    platform,
    COUNT(*) AS count,
    COUNT(*) FILTER (WHERE status = 'Rejected') AS rejected,
    COUNT(*) FILTER (WHERE status IN ('Positive Response', 'Interview', 'Offer')) AS positive
FROM applications
WHERE is_active = true
GROUP BY user_id, platform
ORDER BY count DESC;

ALTER VIEW platform_breakdown SET (security_invoker = true);

-- 3. top_companies
DROP VIEW IF EXISTS top_companies CASCADE;
CREATE OR REPLACE VIEW top_companies AS
SELECT
    user_id,
    company_name,
    COUNT(*) AS applications,
    COUNT(*) FILTER (WHERE status = 'Rejected') AS rejected,
    COUNT(*) FILTER (WHERE status IN ('Positive Response','Interview','Offer')) AS positive,
    MIN(date_applied) AS first_applied
FROM applications
WHERE is_active = true
GROUP BY user_id, company_name
ORDER BY applications DESC;

ALTER VIEW top_companies SET (security_invoker = true);

-- 4. location_breakdown
DROP VIEW IF EXISTS location_breakdown CASCADE;
CREATE OR REPLACE VIEW location_breakdown AS
SELECT
    user_id,
    location,
    COUNT(*) AS count,
    ROUND(
        COUNT(*)::NUMERIC /
        NULLIF(SUM(COUNT(*)) OVER (PARTITION BY user_id), 0) * 100, 1
    ) AS pct
FROM applications
WHERE location != '' AND is_active = true
GROUP BY user_id, location
ORDER BY count DESC;

ALTER VIEW location_breakdown SET (security_invoker = true);

-- 5. conversion_funnel
DROP VIEW IF EXISTS conversion_funnel CASCADE;
CREATE OR REPLACE VIEW conversion_funnel AS
SELECT user_id, 'Applications Submitted' AS stage, COUNT(*) AS count
FROM applications WHERE is_active = true GROUP BY user_id
UNION ALL
SELECT user_id, 'Awaiting Response', COUNT(*)
FROM applications WHERE status = 'Applied' AND is_active = true GROUP BY user_id
UNION ALL
SELECT user_id, 'Positive Response', COUNT(*)
FROM applications WHERE status NOT IN ('Applied', 'Rejected') AND is_active = true GROUP BY user_id
UNION ALL
SELECT user_id, 'Interview', COUNT(*)
FROM applications WHERE status IN ('Interview', 'Offer') AND is_active = true GROUP BY user_id
UNION ALL
SELECT user_id, 'Offer', COUNT(*)
FROM applications WHERE status = 'Offer' AND is_active = true GROUP BY user_id;

ALTER VIEW conversion_funnel SET (security_invoker = true);

-- ══════════════════════════════════════════════════════════════
-- T-003: ADD MISSING RLS POLICIES
-- ══════════════════════════════════════════════════════════════

-- pipeline_tasks
ALTER TABLE pipeline_tasks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own pipeline tasks" ON pipeline_tasks;
CREATE POLICY "Users can view own pipeline tasks"
    ON pipeline_tasks FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own pipeline tasks" ON pipeline_tasks;
CREATE POLICY "Users can insert own pipeline tasks"
    ON pipeline_tasks FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- pipeline_run_steps (via run_id → pipeline_runs.user_id)
ALTER TABLE pipeline_run_steps ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own pipeline steps" ON pipeline_run_steps;
CREATE POLICY "Users can view own pipeline steps"
    ON pipeline_run_steps FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM pipeline_runs
            WHERE pipeline_runs.id = pipeline_run_steps.run_id
            AND pipeline_runs.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can insert own pipeline steps" ON pipeline_run_steps;
CREATE POLICY "Users can insert own pipeline steps"
    ON pipeline_run_steps FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM pipeline_runs
            WHERE pipeline_runs.id = pipeline_run_steps.run_id
            AND pipeline_runs.user_id = auth.uid()
        )
    );

-- ══════════════════════════════════════════════════════════════
-- VERIFICATION
-- ══════════════════════════════════════════════════════════════

SELECT tablename, policyname, cmd
FROM pg_policies
WHERE tablename IN ('pipeline_tasks', 'pipeline_run_steps')
ORDER BY tablename, policyname;
