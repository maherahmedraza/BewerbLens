ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS gmail_connected_via TEXT
        CHECK (gmail_connected_via IN ('oauth', 'env_fallback'));

UPDATE user_profiles
SET gmail_connected_via = CASE
    WHEN gmail_connected_via IS NOT NULL THEN gmail_connected_via
    WHEN gmail_credentials IS NOT NULL THEN 'oauth'
    ELSE NULL
END;

ALTER TABLE email_filters
    ADD COLUMN IF NOT EXISTS is_protected BOOLEAN NOT NULL DEFAULT false;

DO $$
DECLARE
    old_constraint_name TEXT;
BEGIN
    SELECT conname
    INTO old_constraint_name
    FROM pg_constraint
    WHERE conrelid = 'email_filters'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) ILIKE '%filter_type%'
    ORDER BY conname
    LIMIT 1;

    IF old_constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE email_filters DROP CONSTRAINT %I', old_constraint_name);
    END IF;
END;
$$;

ALTER TABLE email_filters
    DROP CONSTRAINT IF EXISTS email_filters_filter_type_check;

ALTER TABLE email_filters
    ADD CONSTRAINT email_filters_filter_type_check
        CHECK (filter_type IN ('include', 'exclude', 'platform_allowlist'));

CREATE OR REPLACE FUNCTION create_default_filters(p_user_id UUID, p_region TEXT)
RETURNS void AS $$
BEGIN
    INSERT INTO email_filters (user_id, filter_type, field, pattern, is_regex, is_protected, priority)
    SELECT p_user_id, defaults.filter_type, defaults.field, defaults.pattern, defaults.is_regex, defaults.is_protected, defaults.priority
    FROM (
        VALUES
            ('platform_allowlist', 'sender', 'jobs-noreply@linkedin.com', false, true, -100),
            ('platform_allowlist', 'sender', 'noreply@xing.com', false, true, -100),
            ('platform_allowlist', 'sender', 'no-reply@stepstone.de', false, true, -100),
            ('platform_allowlist', 'sender', 'noreply@indeed.com', false, true, -100),
            ('platform_allowlist', 'sender', 'noreply@glassdoor.com', false, true, -100)
    ) AS defaults(filter_type, field, pattern, is_regex, is_protected, priority)
    WHERE NOT EXISTS (
        SELECT 1
        FROM email_filters ef
        WHERE ef.user_id = p_user_id
          AND ef.filter_type = defaults.filter_type
          AND ef.field = defaults.field
          AND lower(ef.pattern) = lower(defaults.pattern)
    );

    IF p_region = 'en' THEN
        INSERT INTO email_filters (user_id, filter_type, field, pattern, is_regex, priority)
        SELECT p_user_id, defaults.filter_type, defaults.field, defaults.pattern, defaults.is_regex, defaults.priority
        FROM (
            VALUES
                ('include', 'subject', 'application', false, 1),
                ('include', 'subject', 'applied', false, 1),
                ('include', 'subject', 'confirmation', false, 1),
                ('include', 'subject', 'thank you for applying', false, 1),
                ('include', 'subject', 'we received', false, 1),
                ('include', 'subject', 'interview', false, 2),
                ('include', 'subject', 'offer', false, 2),
                ('include', 'subject', 'rejection', false, 3),
                ('include', 'subject', 'unfortunately', false, 3),
                ('include', 'subject', 'update', false, 4),
                ('include', 'subject', 'status', false, 4),
                ('include', 'subject', 'career', false, 5),
                ('include', 'subject', 'hiring', false, 5),
                ('include', 'subject', 'recruitment', false, 5),
                ('include', 'subject', 'talent', false, 5),
                ('include', 'subject', 'assessment', false, 5),
                ('include', 'subject', 'next steps', false, 5),
                ('include', 'subject', 'candidacy', false, 6),
                ('include', 'subject', 'position', false, 6),
                ('include', 'subject', 'role', false, 6),
                ('include', 'subject', 'action required', false, 6),
                ('exclude', 'sender', 'noreply@linkedin.com', false, 10),
                ('exclude', 'subject', 'job alert', false, 10),
                ('exclude', 'subject', 'jobalert', false, 10),
                ('exclude', 'subject', 'recommended for you', false, 10)
        ) AS defaults(filter_type, field, pattern, is_regex, priority)
        WHERE NOT EXISTS (
            SELECT 1
            FROM email_filters ef
            WHERE ef.user_id = p_user_id
              AND ef.filter_type = defaults.filter_type
              AND ef.field = defaults.field
              AND lower(ef.pattern) = lower(defaults.pattern)
        );
    ELSIF p_region = 'de' THEN
        INSERT INTO email_filters (user_id, filter_type, field, pattern, is_regex, priority)
        SELECT p_user_id, defaults.filter_type, defaults.field, defaults.pattern, defaults.is_regex, defaults.priority
        FROM (
            VALUES
                ('include', 'subject', 'bewerbung', false, 1),
                ('include', 'subject', 'beworben', false, 1),
                ('include', 'subject', 'eingangsbestätigung', false, 1),
                ('include', 'subject', 'bestätigung', false, 1),
                ('include', 'subject', 'interview', false, 2),
                ('include', 'subject', 'gespräch', false, 2),
                ('include', 'subject', 'absage', false, 3),
                ('include', 'subject', 'leider', false, 3),
                ('include', 'subject', 'rückmeldung', false, 3),
                ('include', 'subject', 'update', false, 4),
                ('include', 'subject', 'status', false, 4),
                ('include', 'subject', 'karriere', false, 5),
                ('include', 'subject', 'einstellung', false, 5),
                ('include', 'subject', 'talent', false, 5),
                ('include', 'subject', 'nächste schritte', false, 5),
                ('include', 'subject', 'kandidatur', false, 6),
                ('include', 'subject', 'stelle', false, 6),
                ('include', 'subject', 'position', false, 6),
                ('include', 'subject', 'profil', false, 6),
                ('exclude', 'sender', 'noreply@linkedin.com', false, 10),
                ('exclude', 'subject', 'job alert', false, 10),
                ('exclude', 'subject', 'jobalarm', false, 10),
                ('exclude', 'subject', 'empfehlungen', false, 10)
        ) AS defaults(filter_type, field, pattern, is_regex, priority)
        WHERE NOT EXISTS (
            SELECT 1
            FROM email_filters ef
            WHERE ef.user_id = p_user_id
              AND ef.filter_type = defaults.filter_type
              AND ef.field = defaults.field
              AND lower(ef.pattern) = lower(defaults.pattern)
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

INSERT INTO email_filters (user_id, filter_type, field, pattern, is_regex, is_protected, priority)
SELECT up.id, defaults.filter_type, defaults.field, defaults.pattern, defaults.is_regex, defaults.is_protected, defaults.priority
FROM user_profiles up
CROSS JOIN (
    VALUES
        ('platform_allowlist', 'sender', 'jobs-noreply@linkedin.com', false, true, -100),
        ('platform_allowlist', 'sender', 'noreply@xing.com', false, true, -100),
        ('platform_allowlist', 'sender', 'no-reply@stepstone.de', false, true, -100),
        ('platform_allowlist', 'sender', 'noreply@indeed.com', false, true, -100),
        ('platform_allowlist', 'sender', 'noreply@glassdoor.com', false, true, -100)
) AS defaults(filter_type, field, pattern, is_regex, is_protected, priority)
WHERE NOT EXISTS (
    SELECT 1
    FROM email_filters ef
    WHERE ef.user_id = up.id
      AND ef.filter_type = defaults.filter_type
      AND ef.field = defaults.field
      AND lower(ef.pattern) = lower(defaults.pattern)
);

ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS job_location TEXT,
    ADD COLUMN IF NOT EXISTS job_city TEXT,
    ADD COLUMN IF NOT EXISTS job_country TEXT,
    ADD COLUMN IF NOT EXISTS work_mode TEXT NOT NULL DEFAULT 'Unknown'
        CHECK (work_mode IN ('Remote', 'Hybrid', 'On-site', 'Unknown'));

UPDATE applications
SET
    job_location = COALESCE(NULLIF(job_location, ''), NULLIF(location, '')),
    work_mode = COALESCE(NULLIF(work_mode, ''), 'Unknown');

DROP VIEW IF EXISTS location_breakdown CASCADE;
CREATE OR REPLACE VIEW location_breakdown AS
SELECT
    user_id,
    COALESCE(
        NULLIF(job_city, ''),
        NULLIF(job_country, ''),
        NULLIF(job_location, ''),
        NULLIF(location, ''),
        'Location not specified'
    ) AS location,
    COUNT(*) AS count,
    ROUND(
        COUNT(*)::NUMERIC /
        NULLIF(SUM(COUNT(*)) OVER (PARTITION BY user_id), 0) * 100, 1
    ) AS pct
FROM applications
WHERE is_active = true
GROUP BY 
    user_id, 
    COALESCE(
        NULLIF(job_city, ''),
        NULLIF(job_country, ''),
        NULLIF(job_location, ''),
        NULLIF(location, ''),
        'Location not specified'
    )
ORDER BY count DESC;

ALTER VIEW location_breakdown SET (security_invoker = true);
