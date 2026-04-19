# Task List

## Completed

- Audit the repository against the requested multi-tenant prompt
- Add database support for sync state, telegram link requests, and usage metrics
- Extend tracker/orchestrator runtime for sync-mode-aware execution and usage recording
- Add Gmail OAuth and Telegram linking route handlers in the dashboard
- Refactor Profile and Settings to stop exposing sensitive integration fields
- Fix sidebar profile navigation and add active-state handling
- Add operational analytics backed by `usage_metrics`
- Update environment examples and deployment documentation

## Follow-up items

- Apply migration `010_sync_integrations_analytics.sql` to each Supabase environment
- Configure the new dashboard server-side environment variables in Vercel
- Wire the Telegram bot or webhook caller to `POST /api/integrations/telegram/link/complete`
- Create at least one admin user if cross-user operational analytics are needed
