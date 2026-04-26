# BewerbLens — Architect Remediation & Delivery Plan

## Objective

Turn the architect review into an execution-ready program that hardens BewerbLens for secure multi-user use, reduces production risk, and implements the highest-impact recommendations in a controlled order.

This plan is intentionally phased. The first implementation tranche prioritizes **security, multi-user safety, and production stability** before broader feature work.

---

## Current baseline

### Findings confirmed against the current codebase

| Finding | Current state | Priority |
|---|---|---|
| CORS uses `allow_origins=["*"]` with `allow_credentials=True` in `apps/orchestrator/main.py` | Confirmed | Critical |
| Orchestrator run/config endpoints do not have request authentication | Confirmed | Critical |
| Backend uses `settings.supabase_key` service-role client in tracker storage path | Confirmed and expected for server-side work; needs tighter boundaries and documentation | Critical |
| Gmail credential encryption falls back to plaintext JSON when no encryption secret/key exists | Confirmed in `apps/tracker/gmail_service.py` | Critical |
| `tracker.py` still duplicates `record_usage_metrics()` calls | Confirmed | High |
| No staging backend environment; frontend preview exists on `dev`, backend preview does not | Confirmed | High |
| Test coverage is still thin on tracker orchestration, dashboard flows, and migrations | Confirmed | High |
| Telegram production runtime was disabled globally | Already corrected in `.do/app.yaml`; keep verified in rollout checklist | Closed, monitor |

### Findings that need implementation detail, not blind adoption

1. **Service-role usage** should not be removed outright. The pipeline needs server-side privileged access; the correct fix is to reduce scope, isolate helpers, and document trust boundaries.
2. **Task queue replacement** should not happen in the first tranche. Redis/arq is a later-scale step; near-term fairness controls belong in the current Supabase-backed queue.
3. **All recommendations** should not land in one PR. Security and data safety changes must land first, then refactors/tests, then product expansion.

---

## Delivery principles

1. **Protect production first.** Critical auth/CORS/encryption issues land before refactors or new product features.
2. **Preserve the current architecture.** Keep Supabase as the coordination hub and keep the orchestrator/tracker split intact during the first remediation pass.
3. **Stay multi-user safe.** Any dashboard, API, or pipeline change must preserve user isolation and avoid new service-role exposure in frontend paths.
4. **Ship in narrow phases.** Each phase must be independently reviewable, testable, and deployable.
5. **Prefer durable fixes over cosmetic cleanup.** Refactors must remove root duplication or unsafe behavior, not just move code around.

---

## Phased implementation program

## Phase 0 — Verification, rollback safety, and execution guardrails

### Goal
Freeze the remediation scope, verify environment prerequisites, and define safe rollout/rollback rules before changing production-sensitive code.

### Work

1. Audit current production-sensitive env usage:
   - `SUPABASE_KEY`
   - `ENCRYPTION_SECRET`
   - `ENCRYPTION_KEY`
   - `TELEGRAM_ENABLED`
   - `TELEGRAM_BOT_TOKEN`
   - `ORCHESTRATOR_API_KEY`
   - frontend `NEXT_PUBLIC_*`
2. Define rollout notes for changes that require secret provisioning before deploy.
3. Document which changes require synchronized deploys across dashboard/backend/infra.
4. Record pre-change validation commands and post-change smoke checks.

### Exit criteria

- Required secrets and config dependencies are known.
- The implementation order is locked.
- The team has a clear “do not deploy until secrets exist” checklist.

---

## Phase 1 — Security and multi-user hardening

### Goal
Close the critical production risks without breaking the current UX or queue model.

### Workstream A — CORS and API authentication

1. Replace wildcard CORS with an explicit allowlist sourced from environment and known Vercel origins.
2. Keep `allow_credentials=True`, but only for trusted origins.
3. Add orchestrator request authentication for write endpoints:
   - `/runs/*`
   - `/config/*`
4. Decide whether health/status routes remain public or get separate protection.
5. Update dashboard API callers to send the orchestrator auth secret from server-side routes only; do not expose it in browser code.

### Workstream B — Encryption and credential safety

1. Make encryption secret availability mandatory for backend startup.
2. Remove plaintext fallback storage for Gmail credentials.
3. Keep backwards-compatible decryption for already-stored encrypted/legacy payloads during transition.
4. Add explicit startup failure with actionable error messaging if encryption configuration is missing.
5. Review Telegram credential model:
   - stop storing per-user `telegram_bot_token` in plaintext if still used
   - prefer shared bot + per-user chat link where possible

### Workstream C — Service-role boundary tightening

1. Document which tracker/orchestrator operations require service-role access.
2. Audit backend code so service-role client usage stays server-only and centralized.
3. Reduce scattered privileged DB access patterns where practical.
4. Add comments/docs clarifying that service-role access is an intentional backend trust boundary, not a frontend pattern.

### Workstream D — Operational abuse protection

1. Add basic request throttling or equivalent guard for orchestrator write endpoints.
2. Add safe error responses for unauthorized or malformed requests.
3. Review whether manual trigger/backfill endpoints need per-user cadence caps.

### Exit criteria

- Wildcard credentialed CORS is gone.
- Orchestrator write endpoints require authentication.
- Backend startup fails if encryption configuration is missing.
- No new plaintext Gmail credential writes can occur.
- Service-role usage is documented and scoped.

---

## Phase 2 — Data retention, queue fairness, and production safety

### Goal
Reduce operational and data-growth risk while staying on the existing single-container architecture.

### Workstream A — Retention and cleanup

1. Add retention cleanup for `pipeline_run_logs`.
2. Review retention policy for `raw_emails`, historical run records, and derived telemetry.
3. Ensure cleanup jobs respect multi-user data integrity and auditability needs.

### Workstream B — Queue fairness

1. Add a configurable `max_emails_per_run` guard for large backfills.
2. Define per-user task fairness rules so one very large mailbox does not monopolize the single worker indefinitely.
3. Decide whether large backfills should chunk into multiple tasks or be capped and resumed.

### Workstream C — Migration safety and environment protection

1. Review destructive migrations and document rollout/recovery expectations.
2. Add local/staging-safe migration validation steps before production deploy.
3. Ensure new migrations are reversible where practical or at least operationally recoverable.

### Exit criteria

- Log growth has a retention policy.
- Long backfills no longer have unbounded starvation potential.
- Migration risk is explicitly managed rather than implicit.

---

## Phase 3 — Tracker maintainability refactor

### Goal
Lower change risk in the core pipeline without changing stage contracts or pipeline semantics.

### Work

1. Refactor `tracker.py` by responsibility:
   - pipeline orchestration
   - ingestion stage
   - analysis stage
   - persistence stage
   - shared run-finalization/reporting helpers
2. Remove duplicated `record_usage_metrics()` call sites with a shared recorder/finalization path.
3. Review `gmail_service.py` and separate:
   - encryption helpers
   - credential loading/refresh
   - Gmail fetch/query helpers
4. Standardize English comments/docstrings in the touched modules.
5. Keep persisted `pipeline_run_steps.stats` contracts unchanged.

### Exit criteria

- `tracker.py` no longer acts as an 800+ line catch-all.
- Usage metrics are recorded through one durable pattern.
- Refactor does not change stage sequencing or resume behavior.

---

## Phase 4 — Testing, CI, and validation depth

### Goal
Move from spot checks to reliable regression coverage across backend, dashboard, and migrations.

### Workstream A — Backend tests

1. Add shared fixtures/mocks for:
   - Gmail API
   - Gemini classifier
   - Supabase storage interactions
   - Telegram sender
2. Add tests for critical tracker orchestration paths:
   - happy path full run
   - cancellation
   - partial success
   - notification failure handling
   - status-priority persistence

### Workstream B — Dashboard tests

1. Add tests for the new route structure:
   - public `/`
   - protected `/dashboard`
   - `/profile` redirect to `/settings`
2. Add tests for settings/auth integration surfaces and analytics rendering fallbacks.

### Workstream C — CI hardening

1. Add dependency/security scanning:
   - `pip-audit`
   - `npm audit` (or controlled audit step appropriate for CI noise)
2. Add migration validation workflow or local test target.
3. Keep existing lint/build/test flow green on `dev` and `main`.

### Exit criteria

- Critical pipeline paths have automated regression coverage.
- The dashboard route split has test coverage.
- CI catches dependency/security regressions earlier.

---

## Phase 5 — DevOps and environment maturity

### Goal
Create safer pre-production validation and easier full-stack development.

### Work

1. Add a local full-stack `docker-compose` workflow or equivalent documented local stack.
2. Define a true backend preview/staging environment:
   - separate DigitalOcean app
   - separate Supabase project or protected dataset
   - separate secrets
3. Keep `dev` as preview/integration and `main` as production-only.
4. Document deploy sequencing for backend- and migration-sensitive releases.

### Exit criteria

- Frontend preview is complemented by a backend preview path.
- Local full-stack validation is documented and repeatable.
- Production deploy risk is lower because non-production validation exists.

---

## Phase 6 — Product recommendations after stability work

### Goal
Implement the strongest product wins once the platform is safer to evolve.

### First candidates

1. Follow-up reminders via Telegram.
2. Error boundary + better authenticated loading/error states.
3. Accessibility improvements for charts and navigation.
4. Streaming-safe export improvements if current CSV generation becomes a limit.
5. Stronger operational analytics and delivery telemetry.

### Deferred strategic bets

These remain valuable but should not start before Phases 1-5 are substantially complete:

1. Chrome extension
2. Resume optimizer
3. Calendar integration
4. Coach/recruiter mode
5. Monetization/billing

---

## Cross-phase validation strategy

Each implementation PR or phase should validate the existing repo commands that apply to the change set:

### Backend

```bash
pip install -r requirements.txt
ruff check apps/tracker apps/orchestrator
PYTHONPATH=apps/tracker pytest apps/tracker/tests -v --tb=short
```

### Dashboard

```bash
cd apps/dashboard
npm ci
npm run lint
NEXT_PUBLIC_SUPABASE_URL=https://placeholder.supabase.co \
NEXT_PUBLIC_SUPABASE_ANON_KEY=placeholder_key \
NEXT_PUBLIC_ORCHESTRATOR_URL=http://localhost:8000 \
npm run build
```

### Additional validation expected during implementation

1. Route/auth smoke checks for public vs protected pages
2. Manual verification of orchestrator auth failures/successes
3. Secret-missing startup failure checks for backend encryption configuration
4. Telegram end-of-run report verification after secure credential-path changes

---

## Recommended implementation order

1. Phase 0 — verification and rollout guardrails
2. Phase 1 — security and multi-user hardening
3. Phase 2 — retention, queue fairness, and migration safety
4. Phase 3 — tracker maintainability refactor
5. Phase 4 — testing and CI depth
6. Phase 5 — DevOps/staging maturity
7. Phase 6 — product recommendations

---

## Notes

- The architect report is directionally right, but implementation should be based on the **current codebase**, not assumed stale findings.
- The recent dashboard information-architecture changes remain valid: `/dashboard` stays operational, `/analytics` stays the chart-heavy hub, and `/settings` remains the single configuration workspace.
- The remediation program should preserve the current Supabase-centered design until scale or cost justifies deeper platform changes.
