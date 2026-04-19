# Multi-Tenant Transformation Plan

## Problem

BewerbLens already had substantial multi-user groundwork in Supabase, the tracker, and the orchestrator, but the user-facing product still exposed integration-sensitive fields in the browser, relied on stale single-user environment assumptions in docs, and lacked operational analytics for sync usage.

## Approach

1. Preserve the existing split architecture: Next.js handles authenticated user flows, while the FastAPI orchestrator and tracker remain responsible for background execution.
2. Add per-user sync state and usage telemetry in the database and pipeline runtime.
3. Move Gmail and Telegram connection flows behind server-side routes so secrets never need to be edited from the browser.
4. Expand the dashboard with sync controls and operational analytics, then align docs and environment examples with the new flow.

## Workstreams

### 1. Backend and schema
- Add sync-mode and sync-status fields to `user_profiles`
- Persist usage metrics for Gmail, Gemini, Telegram, and run outcomes
- Update orchestrator scheduling and worker finalization for per-user sync behavior

### 2. Secure integration flows
- Add Gmail OAuth start/callback route handlers
- Add Telegram link start/complete route handlers
- Store encrypted Gmail credentials server-side

### 3. Dashboard UX
- Remove client-side secret handling from Profile
- Add sync controls to Settings
- Fix profile navigation in the sidebar
- Add operational analytics on the Analytics page

### 4. Docs and deployment
- Refresh environment examples for dashboard and backend surfaces
- Update deployment instructions and migration order
- Record the transformation plan, task list, env inventory, and delivery report
