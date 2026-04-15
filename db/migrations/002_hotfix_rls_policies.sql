-- ╔══════════════════════════════════════════════════════════════╗
-- ║  Post-Migration Hotfix                                      ║
-- ║                                                             ║
-- ║  1. Drop "Allow public read" — defeats RLS on applications  ║
-- ║  2. Add INSERT policy on user_profiles for client upsert    ║
-- ╚══════════════════════════════════════════════════════════════╝

-- 1. Remove the pre-existing open-access SELECT policy on applications.
--    With this policy active, auth.uid() check is ORed with "true",
--    meaning ALL rows are visible to ALL users — defeating multi-user isolation.
DROP POLICY IF EXISTS "Allow public read" ON applications;

-- 2. Allow authenticated users to insert their own profile row.
--    Needed for the client-side upsert fallback in profile/page.tsx
--    when the handle_new_user trigger didn't fire.
DROP POLICY IF EXISTS "Users can insert own profile" ON user_profiles;
CREATE POLICY "Users can insert own profile"
    ON user_profiles FOR INSERT
    WITH CHECK (auth.uid() = id);

-- Verification: confirm "Allow public read" is gone and new INSERT policy exists
SELECT tablename, policyname, cmd, qual
FROM pg_policies
WHERE tablename IN ('applications', 'user_profiles')
ORDER BY tablename, policyname;
