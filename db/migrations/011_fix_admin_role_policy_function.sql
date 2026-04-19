-- ╔══════════════════════════════════════════════════════════════╗
-- ║  Migration 011 — Fix admin role policy function reference   ║
-- ║                                                             ║
-- ║  Migration 010 created public.get_user_role() but the new   ║
-- ║  RLS policies referenced auth.get_user_role(), which does   ║
-- ║  not exist and blocks reads from user_profiles.             ║
-- ╚══════════════════════════════════════════════════════════════╝

CREATE OR REPLACE FUNCTION public.get_user_role()
RETURNS TEXT
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT role
  FROM public.user_profiles
  WHERE id = auth.uid();
$$;

DROP POLICY IF EXISTS "Admins can view all profiles" ON user_profiles;
CREATE POLICY "Admins can view all profiles"
    ON user_profiles FOR SELECT
    USING (
        public.get_user_role() = 'admin'
    );

DROP POLICY IF EXISTS "Admins can view all usage metrics" ON usage_metrics;
CREATE POLICY "Admins can view all usage metrics"
    ON usage_metrics FOR SELECT
    USING (
        public.get_user_role() = 'admin'
    );
