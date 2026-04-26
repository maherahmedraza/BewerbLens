# Current Debug + Future Development Program

## Current production/debug problems

### 1. Sankey analytics regression

- The uncommitted dashboard changes add a new `StatusFlowSankey` chart to `apps/dashboard/src/app/page.tsx`.
- The investigation scope is the new chart component, the `buildStatusFlowSankey()` transformer, and the changed type surface in `apps/dashboard/src/lib/types.ts`.
- Immediate goal: isolate the exact build/runtime issue, fix the regression, and keep the dashboard overview page rendering even if Sankey data is empty or malformed.

### 2. Telegram run report not delivered

- The pipeline only sends the end-of-run Telegram report when the user profile is enabled and the tracker sender path is allowed to execute.
- The current deployment config in `.do/app.yaml` sets `TELEGRAM_ENABLED` to `"false"`, which disables the tracker notification path in production even when a user has linked Telegram.
- Immediate goal: align runtime gating with the product UX so a linked-and-enabled user actually receives the consolidated end-of-run report.

## Immediate implementation approach

### A. Stabilize the Sankey feature

1. Confirm the precise build/runtime failure introduced by the current working tree.
2. Fix the failing chart integration without changing unrelated dashboard behavior.
3. Keep the chart resilient to empty histories, unknown statuses, and small-screen layouts.
4. Add or update dashboard validation so the regression is caught before deploy.

### B. Restore Telegram delivery

1. Trace the full flow: dashboard link request -> `user_profiles` data -> tracker notification gate -> Telegram sender.
2. Remove any incorrect global-only gating that blocks a user-linked Telegram report.
3. Ensure production config documents the required backend env vars clearly.
4. Preserve the existing consolidated end-of-run report behavior; do not reintroduce per-email spam.

## Highest-impact future development program

### 1. Pipeline reliability and observability

- Add stronger run diagnostics around each stage, especially artifact loading, downstream stage inputs, and notification failures.
- Surface run summaries, error categories, and notification outcomes directly in the dashboard.
- Add clear operator signals for partial-success runs, zombie cleanup events, and third-party API failures.

### 2. Gmail ingestion quality

- Improve first-run discovery and incremental sync confidence without reintroducing `is:unread`.
- Add better visibility into filtered vs persisted emails so users can understand what the pipeline ignored and why.
- Strengthen platform-specific sender handling and audit allowlist coverage for major job boards.

### 3. Analytics product surface

- Complete the Sankey flow visualization and pair it with drill-down tables for the applications behind each transition.
- Add richer trend analytics: response rate, rejection latency, interview conversion, and offer conversion by month/platform/location.
- Add exportable analytics snapshots for reporting outside the app.

### 4. Notifications and user communication

- Add a delivery status surface for Telegram with last sent timestamp, last failure reason, and a test-send action.
- Expand notification channels only after delivery telemetry exists, prioritizing reliability over channel count.
- Add finer-grained notification preferences while keeping end-of-run summaries as the default.

### 5. Multi-user operations and admin tooling

- Improve admin visibility into sync health across users without violating RLS boundaries.
- Add tools for requeue, rerun-stage, and failure triage from the dashboard using existing orchestrator endpoints.
- Add safe audit views for linked integrations, sync freshness, and usage/cost trends.

### 6. Data quality and application intelligence

- Strengthen status-history quality so visualizations and exports reflect actual lifecycle transitions.
- Improve company/job-title normalization to reduce duplicate records.
- Add confidence review workflows for borderline classifications and fuzzy matches.

### 7. Growth-facing UX improvements

- Make onboarding clearer around Gmail connect, first run, Telegram linking, and expected processing time.
- Add CSV/XLSX/Google Sheets export workflows for applications and analytics.
- Improve mobile dashboard usability, chart readability, and empty/error states.

## Prioritization

1. Fix current regressions: Sankey rendering and Telegram report delivery.
2. Add dashboard/operator visibility for pipeline and notification health.
3. Improve analytics depth and export value.
4. Improve data quality and classification confidence tooling.
5. Expand admin and multi-user operational workflows.

## Notes

- All fixes must preserve the existing Supabase-centered multi-user architecture.
- Dashboard live updates should continue to rely on Supabase Realtime rather than orchestrator polling.
- Tracker stage contracts must continue to use persisted `pipeline_run_steps.stats` artifacts.
