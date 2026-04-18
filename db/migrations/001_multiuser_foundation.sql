-- ╔══════════════════════════════════════════════════════════════╗
-- ║  BewerbLens Multi-User System Migration (IDEMPOTENT)       ║
-- ║                                                             ║
-- ║  Safe to re-run: all statements are guarded with           ║
-- ║  DROP IF EXISTS / IF NOT EXISTS / CREATE OR REPLACE        ║
-- ║                                                             ║
-- ║  Based on: temp/migration_multiuser.sql                    ║
-- ╚══════════════════════════════════════════════════════════════╝

-- ══════════════════════════════════════════════════════════════
-- 1. USER PROFILES TABLE
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    region TEXT DEFAULT 'en' CHECK (region IN ('en', 'de', 'fr', 'es')),

    -- Email provider configurations
    gmail_credentials JSONB,
    outlook_credentials JSONB,

    -- Feature flags
    telegram_enabled BOOLEAN DEFAULT false,
    telegram_bot_token TEXT,
    telegram_chat_id TEXT,

    -- Preferences
    timezone TEXT DEFAULT 'UTC',
    language TEXT DEFAULT 'en',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- Idempotent policy creation: drop then create
DROP POLICY IF EXISTS "Users can view own profile" ON user_profiles;
CREATE POLICY "Users can view own profile"
    ON user_profiles FOR SELECT
    USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can insert own profile" ON user_profiles;
CREATE POLICY "Users can insert own profile"
    ON user_profiles FOR INSERT
    WITH CHECK (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;
CREATE POLICY "Users can update own profile"
    ON user_profiles FOR UPDATE
    USING (auth.uid() = id);

-- Auto-create profile when user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, email)
    VALUES (NEW.id, NEW.email);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ══════════════════════════════════════════════════════════════
-- 2. EMAIL FILTERS TABLE
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS email_filters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    filter_type TEXT NOT NULL CHECK (filter_type IN ('include', 'exclude')),
    field TEXT NOT NULL CHECK (field IN ('subject', 'sender', 'body')),
    pattern TEXT NOT NULL,

    is_regex BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE email_filters ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage own filters" ON email_filters;
CREATE POLICY "Users can manage own filters"
    ON email_filters FOR ALL
    USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_email_filters_user ON email_filters(user_id);
CREATE INDEX IF NOT EXISTS idx_email_filters_active ON email_filters(user_id, is_active);

-- ══════════════════════════════════════════════════════════════
-- 3. DEFAULT FILTERS BY REGION
-- ══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION create_default_filters(p_user_id UUID, p_region TEXT)
RETURNS void AS $$
BEGIN
    IF p_region = 'en' THEN
        INSERT INTO email_filters (user_id, filter_type, field, pattern, is_regex, priority) VALUES
        (p_user_id, 'include', 'subject', 'application', false, 1),
        (p_user_id, 'include', 'subject', 'applied', false, 1),
        (p_user_id, 'include', 'subject', 'confirmation', false, 1),
        (p_user_id, 'include', 'subject', 'thank you for applying', false, 1),
        (p_user_id, 'include', 'subject', 'interview', false, 2),
        (p_user_id, 'include', 'subject', 'offer', false, 2),
        (p_user_id, 'include', 'subject', 'rejection', false, 3),
        (p_user_id, 'include', 'subject', 'unfortunately', false, 3),
        (p_user_id, 'include', 'subject', 'regret to inform', false, 3),
        (p_user_id, 'exclude', 'sender', 'noreply@linkedin.com', false, 10),
        (p_user_id, 'exclude', 'subject', 'job alert', false, 10),
        (p_user_id, 'exclude', 'subject', 'recommended for you', false, 10);

    ELSIF p_region = 'de' THEN
        INSERT INTO email_filters (user_id, filter_type, field, pattern, is_regex, priority) VALUES
        (p_user_id, 'include', 'subject', 'bewerbung', false, 1),
        (p_user_id, 'include', 'subject', 'beworben', false, 1),
        (p_user_id, 'include', 'subject', 'eingangsbestätigung', false, 1),
        (p_user_id, 'include', 'subject', 'bestätigung', false, 1),
        (p_user_id, 'include', 'subject', 'interview', false, 2),
        (p_user_id, 'include', 'subject', 'gespräch', false, 2),
        (p_user_id, 'include', 'subject', 'absage', false, 3),
        (p_user_id, 'include', 'subject', 'leider', false, 3),
        (p_user_id, 'include', 'subject', 'rückmeldung', false, 3),
        (p_user_id, 'exclude', 'sender', 'noreply@linkedin.com', false, 10),
        (p_user_id, 'exclude', 'subject', 'jobalarm', false, 10),
        (p_user_id, 'exclude', 'subject', 'empfohlen', false, 10);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ══════════════════════════════════════════════════════════════
-- 4. UPDATE EXISTING TABLES WITH USER_ID
-- ══════════════════════════════════════════════════════════════

ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE raw_emails
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE pipeline_runs
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE pipeline_tasks
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_applications_user ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_raw_emails_user ON raw_emails(user_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_user ON pipeline_runs(user_id);

-- ══════════════════════════════════════════════════════════════
-- 5. ROW LEVEL SECURITY POLICIES
-- ══════════════════════════════════════════════════════════════

-- Applications
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;

-- Remove pre-existing open-access policy that defeats RLS
DROP POLICY IF EXISTS "Allow public read" ON applications;

DROP POLICY IF EXISTS "Users can view own applications" ON applications;
CREATE POLICY "Users can view own applications"
    ON applications FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own applications" ON applications;
CREATE POLICY "Users can insert own applications"
    ON applications FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own applications" ON applications;
CREATE POLICY "Users can update own applications"
    ON applications FOR UPDATE
    USING (auth.uid() = user_id);

-- Raw Emails
ALTER TABLE raw_emails ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own emails" ON raw_emails;
CREATE POLICY "Users can view own emails"
    ON raw_emails FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own emails" ON raw_emails;
CREATE POLICY "Users can insert own emails"
    ON raw_emails FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Pipeline Runs
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own pipeline runs" ON pipeline_runs;
CREATE POLICY "Users can view own pipeline runs"
    ON pipeline_runs FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own pipeline runs" ON pipeline_runs;
CREATE POLICY "Users can insert own pipeline runs"
    ON pipeline_runs FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Pipeline Run Logs
ALTER TABLE pipeline_run_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own pipeline logs" ON pipeline_run_logs;
CREATE POLICY "Users can view own pipeline logs"
    ON pipeline_run_logs FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM pipeline_runs
            WHERE pipeline_runs.id = pipeline_run_logs.run_id
            AND pipeline_runs.user_id = auth.uid()
        )
    );

-- ══════════════════════════════════════════════════════════════
-- 6. HELPER FUNCTIONS
-- ══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION get_user_filters(p_user_id UUID)
RETURNS TABLE(
    filter_type TEXT,
    field TEXT,
    pattern TEXT,
    is_regex BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ef.filter_type,
        ef.field,
        ef.pattern,
        ef.is_regex
    FROM email_filters ef
    WHERE ef.user_id = p_user_id
    AND ef.is_active = true
    ORDER BY ef.priority ASC, ef.created_at ASC;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION initialize_user(
    p_user_id UUID,
    p_region TEXT DEFAULT 'en'
)
RETURNS void AS $$
BEGIN
    UPDATE user_profiles
    SET region = p_region
    WHERE id = p_user_id;

    PERFORM create_default_filters(p_user_id, p_region);

    RAISE NOTICE 'User % initialized with region %', p_user_id, p_region;
END;
$$ LANGUAGE plpgsql;

-- ══════════════════════════════════════════════════════════════
-- 7. MIGRATION: Assign existing data to first user
-- ══════════════════════════════════════════════════════════════

DO $$
DECLARE
    first_user_id UUID;
BEGIN
    SELECT id INTO first_user_id
    FROM auth.users
    ORDER BY created_at ASC
    LIMIT 1;

    IF first_user_id IS NOT NULL THEN
        UPDATE applications SET user_id = first_user_id WHERE user_id IS NULL;
        UPDATE raw_emails SET user_id = first_user_id WHERE user_id IS NULL;
        UPDATE pipeline_runs SET user_id = first_user_id WHERE user_id IS NULL;
        UPDATE pipeline_tasks SET user_id = first_user_id WHERE user_id IS NULL;

        RAISE NOTICE 'Assigned existing data to user %', first_user_id;
    END IF;
END;
$$;

-- ══════════════════════════════════════════════════════════════
-- 8. UPDATED STATISTICS VIEWS (Per-User)
-- ══════════════════════════════════════════════════════════════

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
        COUNT(*) FILTER (WHERE status IN ('Positive Response', 'Interview', 'Offer') AND is_active = true)::NUMERIC
        / NULLIF(COUNT(*) FILTER (WHERE is_active = true), 0) * 100, 1
    ) AS success_rate_pct
FROM applications
GROUP BY user_id;

ALTER VIEW application_stats SET (security_invoker = true);

-- ══════════════════════════════════════════════════════════════
-- VERIFICATION
-- ══════════════════════════════════════════════════════════════

SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual
FROM pg_policies
WHERE tablename IN ('applications', 'raw_emails', 'pipeline_runs', 'user_profiles', 'email_filters', 'pipeline_run_logs')
ORDER BY tablename, policyname;
