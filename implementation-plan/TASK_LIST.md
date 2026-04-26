# Task List — Architect Remediation Program

## Phase 0 — Verification and rollout guardrails

1. Inventory all secrets and runtime flags required for remediation.
2. Verify which architect findings are still present in the current code.
3. Define rollout blockers for auth, encryption, and deployment changes.
4. Document pre-deploy and post-deploy smoke checks.

## Phase 1 — Security and multi-user hardening

1. Replace wildcard credentialed CORS with explicit trusted origins.
2. Add authentication to orchestrator write endpoints.
3. Update dashboard/orchestrator integration so secrets remain server-side only.
4. Make backend encryption secret mandatory at startup.
5. Remove plaintext Gmail credential write fallback.
6. Preserve compatible reads for already-stored legacy/encrypted Gmail credentials.
7. Audit and reduce plaintext Telegram bot-token usage.
8. Review and document service-role usage boundaries.
9. Add request throttling or equivalent abuse protection for orchestrator writes.

## Phase 2 — Retention, fairness, and migration safety

1. Add retention cleanup for `pipeline_run_logs`.
2. Review retention expectations for `raw_emails` and telemetry tables.
3. Add `max_emails_per_run` or equivalent cap for large backfills.
4. Define per-user queue fairness behavior on the single worker.
5. Review destructive migrations and document safe rollout expectations.
6. Add migration validation to local/CI workflow where practical.

## Phase 3 — Tracker maintainability refactor

1. Extract tracker orchestration helpers out of `tracker.py`.
2. Deduplicate `record_usage_metrics()` into a shared finalization path.
3. Split Gmail auth/encryption/fetch responsibilities into smaller helpers.
4. Standardize touched comments/docstrings to English.
5. Keep stage ordering and persisted stats contracts unchanged.

## Phase 4 — Testing and CI depth

1. Add reusable backend fixtures for Gmail, Gemini, Supabase, and Telegram mocks.
2. Add tests for tracker happy path, cancellation, partial success, and notification failures.
3. Add dashboard tests for public/protected routing and `/profile` redirect behavior.
4. Add tests for analytics/settings fallback states.
5. Add dependency/security scanning in CI.
6. Add migration validation coverage or dedicated smoke target.

## Phase 5 — DevOps and environment maturity

1. Add/document a local full-stack dev workflow.
2. Define a true backend preview/staging environment for `dev`.
3. Document preview vs production deploy responsibilities.
4. Add release notes/runbook guidance for secret-dependent changes.

## Phase 6 — Product quick wins after stability

1. Add Telegram follow-up reminders.
2. Add authenticated error boundaries and stronger loading/error states.
3. Improve accessibility for charts and navigation.
4. Reassess CSV export path for large datasets.
5. Add richer operational notification telemetry.

## Execution order

1. Phase 0 — verification and rollout guardrails
2. Phase 1 — security and multi-user hardening
3. Phase 2 — retention, fairness, and migration safety
4. Phase 3 — tracker maintainability refactor
5. Phase 4 — testing and CI depth
6. Phase 5 — DevOps and environment maturity
7. Phase 6 — product quick wins

## Success gates

1. No credentialed wildcard CORS
2. Authenticated orchestrator write surface
3. No plaintext Gmail credential writes
4. Stable multi-user-safe queue behavior on large backfills
5. Increased regression coverage across tracker and dashboard
6. Safer pre-production validation path than today
