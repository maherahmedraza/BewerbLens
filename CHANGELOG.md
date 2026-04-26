# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- **Public landing page** at `/` — feature highlights, trust stats, and auth-aware CTA. No sidebar/header chrome.
- **Authenticated dashboard** at `/dashboard` — operational overview with spotlight cards, quick actions, pipeline health signals, top companies, and location mix.
- **Sankey status flow chart** — custom Recharts Sankey component (`StatusFlowSankey`) with typed nodes/links, status-aware coloring, and summary chips. Integrated into the analytics hub.
- **Sankey data pipeline** — server-side `buildStatusFlowSankey()` and `buildStatusSequence()` in `applications.ts` reconstruct chronological status journeys from `status_history` entries.
- **New types**: `SankeyFlowNode`, `SankeyFlowLink`, `StatusFlowSankeyData`, `StatusFlowSankeySummary` in `types.ts`.
- **AppShell component** — client layout switch between public (no sidebar) and authenticated (sidebar + header) views.
- **WorkspaceSettings component** — extracted from the old `/profile` page into a reusable component consumed by `/settings`.
- **Vercel preview deploy workflow** (`deploy-preview.yml`) — deploys frontend previews from the `dev` branch after CI passes.
- **Branching & Release Flow section** in README — documents the new `dev`/`main` two-branch strategy.
- **CHANGELOG.md** — this file.

### Changed
- **CI triggers** — now runs on both `main` and `dev` branches (was `main, feat/*, fix/*, docs/*`).
- **Dashboard information architecture** — `/` is public, `/dashboard` is the operational overview, `/analytics` is the single analytics hub, `/settings` consolidates all account/integration/sync/privacy controls.
- **Typography system** — replaced Geist Sans/Mono with Instrument Sans (body), Fraunces (display), and IBM Plex Mono.
- **Design tokens** — larger border radii (24px/12px), wider sidebar (280px), diffused atmospheric shadows, semi-transparent glassmorphic surfaces.
- **Sidebar navigation** — Dashboard link now points to `/dashboard`; footer user link points to `/settings` with role badge; logo shows "BewerbLens / Private workspace".
- **Analytics page** — now serves as the single insights hub with insight cards, monthly trends, funnel, platform breakdown, Sankey flow, and usage analytics.
- **Settings page** — now includes sync controls, pipeline config, GDPR export/delete, plus the embedded WorkspaceSettings component.
- **README** — updated architecture diagram, CI/CD flow, project structure, and quick start instructions.
- **copilot-instructions.md** — new §8.8 (dashboard IA), updated §9.1 (deploy-preview workflow), new §9.2 (branch strategy), new anti-patterns.
- **docs/deployment.md** — updated CI/CD table, deploy flow diagram, and post-deployment verification steps.
- **docs/architecture.md** — expanded Dashboard Frontend section with new page descriptions, AppShell, and design system.

### Fixed
- **Telegram delivery blocked** — `.do/app.yaml` `TELEGRAM_ENABLED` changed from `"false"` to `"true"`, unblocking end-of-run Telegram reports.
- **Profile→Settings redirect** — `/profile` now redirects to `/settings` instead of being a parallel settings surface.
