-- ╔══════════════════════════════════════════════════════════════╗
-- ║  Migration 010 — Sync State, Linking, and Usage Metrics     ║
-- ║                                                             ║
-- ║  Adds per-user sync tracking, admin role support, bot-based ║
-- ║  Telegram linking state, and operational usage metrics.     ║
-- ╚══════════════════════════════════════════════════════════════╝

ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user'
        CHECK (role IN ('user', 'admin')),
    ADD COLUMN IF NOT EXISTS backfill_start_date DATE,
    ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS sync_mode TEXT NOT NULL DEFAULT 'backfill'
        CHECK (sync_mode IN ('backfill', 'incremental')),
    ADD COLUMN IF NOT EXISTS sync_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (sync_status IN ('pending', 'running', 'complete', 'failed')),
    ADD COLUMN IF NOT EXISTS sync_error TEXT,
    ADD COLUMN IF NOT EXISTS gmail_connected_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS telegram_connected_at TIMESTAMPTZ;

UPDATE user_profiles up
SET
    backfill_start_date = COALESCE(
        up.backfill_start_date,
        COALESCE(
            (SELECT MIN(a.date_applied) FROM applications a WHERE a.user_id = up.id),
            (CURRENT_DATE - INTERVAL '6 months')::date
        )
    ),
    last_synced_at = COALESCE(
        up.last_synced_at,
        (SELECT MAX(COALESCE(a.last_updated, a.processed_at)) FROM applications a WHERE a.user_id = up.id)
    ),
    sync_mode = CASE
        WHEN up.gmail_credentials IS NOT NULL AND up.sync_mode = 'backfill' THEN 'incremental'
        ELSE up.sync_mode
    END,
    sync_status = CASE
        WHEN up.gmail_credentials IS NOT NULL AND up.sync_status = 'pending' THEN 'complete'
        ELSE up.sync_status
    END,
    gmail_connected_at = COALESCE(up.gmail_connected_at, CASE WHEN up.gmail_credentials IS NOT NULL THEN up.updated_at ELSE NULL END),
    telegram_connected_at = COALESCE(up.telegram_connected_at, CASE WHEN up.telegram_chat_id IS NOT NULL AND up.telegram_chat_id <> '' THEN up.updated_at ELSE NULL END);

CREATE INDEX IF NOT EXISTS idx_user_profiles_sync_state ON user_profiles(sync_mode, sync_status);
CREATE INDEX IF NOT EXISTS idx_user_profiles_role ON user_profiles(role);

CREATE TABLE IF NOT EXISTS telegram_link_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    link_code TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'completed', 'expired')),
    telegram_chat_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ
);

ALTER TABLE telegram_link_requests ENABLE ROW LEVEL SECURITY;

-- Fix Infinite Recursion: Create a SECURITY DEFINER function to bypass RLS when checking roles
CREATE OR REPLACE FUNCTION public.get_user_role()
RETURNS TEXT
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT role FROM user_profiles WHERE id = auth.uid();
$$;

DROP POLICY IF EXISTS "Admins can view all profiles" ON user_profiles;
CREATE POLICY "Admins can view all profiles"
    ON user_profiles FOR SELECT
    USING (
        public.get_user_role() = 'admin'
    );

DROP POLICY IF EXISTS "Users can view own telegram link requests" ON telegram_link_requests;
CREATE POLICY "Users can view own telegram link requests"
    ON telegram_link_requests FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own telegram link requests" ON telegram_link_requests;
CREATE POLICY "Users can insert own telegram link requests"
    ON telegram_link_requests FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own telegram link requests" ON telegram_link_requests;
CREATE POLICY "Users can update own telegram link requests"
    ON telegram_link_requests FOR UPDATE
    USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_telegram_link_requests_user ON telegram_link_requests(user_id, status);
CREATE INDEX IF NOT EXISTS idx_telegram_link_requests_code ON telegram_link_requests(link_code);

CREATE TABLE IF NOT EXISTS usage_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    run_id UUID UNIQUE REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    recorded_for DATE NOT NULL DEFAULT CURRENT_DATE,
    emails_processed INTEGER NOT NULL DEFAULT 0 CHECK (emails_processed >= 0),
    gmail_api_calls INTEGER NOT NULL DEFAULT 0 CHECK (gmail_api_calls >= 0),
    gmail_remaining_quota_estimate INTEGER,
    ai_requests INTEGER NOT NULL DEFAULT 0 CHECK (ai_requests >= 0),
    ai_input_tokens_est INTEGER NOT NULL DEFAULT 0 CHECK (ai_input_tokens_est >= 0),
    ai_output_tokens_est INTEGER NOT NULL DEFAULT 0 CHECK (ai_output_tokens_est >= 0),
    ai_estimated_cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    telegram_notifications_sent INTEGER NOT NULL DEFAULT 0 CHECK (telegram_notifications_sent >= 0),
    telegram_notifications_failed INTEGER NOT NULL DEFAULT 0 CHECK (telegram_notifications_failed >= 0),
    success_count INTEGER NOT NULL DEFAULT 0 CHECK (success_count >= 0),
    failure_count INTEGER NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
    error_categories JSONB NOT NULL DEFAULT '{}'::jsonb,
    sync_status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE usage_metrics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own usage metrics" ON usage_metrics;
CREATE POLICY "Users can view own usage metrics"
    ON usage_metrics FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Admins can view all usage metrics" ON usage_metrics;
CREATE POLICY "Admins can view all usage metrics"
    ON usage_metrics FOR SELECT
    USING (
        public.get_user_role() = 'admin'
    );

DROP POLICY IF EXISTS "Users can insert own usage metrics" ON usage_metrics;
CREATE POLICY "Users can insert own usage metrics"
    ON usage_metrics FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_usage_metrics_user_recorded_for ON usage_metrics(user_id, recorded_for DESC);
CREATE INDEX IF NOT EXISTS idx_usage_metrics_created_at ON usage_metrics(created_at DESC);
