# Database Migrations

Run these migrations **in order** against your Supabase PostgreSQL instance.
All migrations are idempotent — safe to re-run.

| # | File | Description |
|---|------|-------------|
| 001 | `001_multiuser_foundation.sql` | Tables, RLS, triggers, functions, user_id columns, backfill |
| 002 | `002_hotfix_rls_policies.sql` | Removes "Allow public read" policy, adds INSERT on user_profiles |
| 003 | `003_views_and_rls.sql` | Updates 5 analytics views for multi-user, RLS on pipeline_tasks/steps |
| 004 | `004_application_stats_view.sql` | Expands application_stats with individual status columns + response_rate |

## Usage

Run via Supabase SQL Editor or `psql`:

```bash
psql "$DATABASE_URL" -f db/migrations/001_multiuser_foundation.sql
psql "$DATABASE_URL" -f db/migrations/002_hotfix_rls_policies.sql
psql "$DATABASE_URL" -f db/migrations/003_views_and_rls.sql
psql "$DATABASE_URL" -f db/migrations/004_application_stats_view.sql
```
