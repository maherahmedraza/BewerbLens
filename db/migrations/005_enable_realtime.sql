-- ╔══════════════════════════════════════════════════════════════╗
-- ║  Migration 005 — Enable Supabase Realtime on pipeline tables║
-- ║                                                             ║
-- ║  Without this, the dashboard cannot receive live updates    ║
-- ║  for pipeline progress, steps, or logs.                     ║
-- ╚══════════════════════════════════════════════════════════════╝

-- Enable Realtime for pipeline monitoring tables
-- These are idempotent — Supabase ignores if already added
DO $$
BEGIN
  BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE pipeline_runs;
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
  
  BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE pipeline_run_steps;
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
  
  BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE pipeline_run_logs;
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
  
  BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE pipeline_tasks;
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
END $$;
