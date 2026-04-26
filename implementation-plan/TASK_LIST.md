# Task List

## Immediate debug tasks

1. Confirm the exact Sankey regression in the current uncommitted dashboard changes.
2. Fix the dashboard regression without breaking the overview page.
3. Trace the Telegram report flow from profile linking to tracker send logic.
4. Fix Telegram report delivery so linked users receive the consolidated end-of-run summary.
5. Validate the dashboard/backend paths affected by these fixes.

## High-impact next features

1. Add pipeline health and notification telemetry to the dashboard.
2. Add richer analytics and transition drill-downs around the application lifecycle.
3. Add export workflows for applications and analytics.
4. Improve data quality for status history, company normalization, and duplicate handling.
5. Improve first-run onboarding and sync-state guidance for new users.
6. Add admin/operator workflows for reruns, failure triage, and sync monitoring.

## Execution order

1. Sankey regression diagnosis and fix
2. Telegram delivery diagnosis and fix
3. Validation and deployment readiness
4. Pipeline observability
5. Analytics depth and exports
6. Data quality improvements
7. Admin/operational workflows

## Notes

- Preserve the existing multi-user Supabase + orchestrator + tracker architecture.
- Keep the Telegram behavior as one consolidated report per run.
- Prefer improvements that increase user trust: reliability, transparency, and actionable analytics.
