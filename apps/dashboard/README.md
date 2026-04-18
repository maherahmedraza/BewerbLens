# BewerbLens Dashboard

The Next.js 16 (App Router) frontend for BewerbLens. Provides real-time pipeline monitoring, application analytics, and pipeline configuration management.

## Pages

| Route | Description |
|---|---|
| `/` | Home / overview |
| `/pipeline` | Pipeline monitor, execution history, and config panel |
| `/applications` | Searchable application table |
| `/analytics` | Charts — monthly trend, platform breakdown, status funnel |
| `/settings` | User settings |
| `/profile` | Profile & Supabase connectivity check |
| `/login` | Supabase Auth login |

## Key Hooks (`src/hooks/usePipeline.ts`)

| Hook | Purpose |
|---|---|
| `useCurrentConfig()` | Fetches `pipeline_config` from Orchestrator |
| `usePipelineRuns(limit)` | Fetches run history; polls every 3 s while a run is active |
| `useTriggerRun()` | POSTs to `/runs/trigger` with the current user's ID |
| `useUpdateConfig()` | PATCHes `/config/` with optimistic UI updates |
| `useRealtimePipeline()` | Subscribes to Supabase Realtime on `pipeline_runs` and `pipeline_config` |

## Environment Variables

```env
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
NEXT_PUBLIC_ORCHESTRATOR_URL=http://localhost:8000
```

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Production

The dashboard is optimised for deployment on [Vercel](https://vercel.com). Set the root directory to `apps/dashboard` and supply the three environment variables above. See [docs/deployment.md](../../docs/deployment.md) for full instructions.
