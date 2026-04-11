-- ╔══════════════════════════════════════════════════════════════╗
-- ║  BewerbLens Migration 0006 — Atomic Task Claiming          ║
-- ║  Fixes: Issue #7 (Race condition via FOR UPDATE SKIP LOCKED)║
-- ╚══════════════════════════════════════════════════════════════╝

-- Add claimed_by column if it doesn't exist
ALTER TABLE pipeline_tasks ADD COLUMN IF NOT EXISTS claimed_by TEXT;

CREATE OR REPLACE FUNCTION claim_next_task(worker_val TEXT DEFAULT NULL)
RETURNS SETOF pipeline_tasks AS $$
DECLARE
  next_task_id uuid;
BEGIN
  -- 1. Atomically pick and lock one pending task.
  -- SKIP LOCKED ensures that if worker A is currently processing a task, 
  -- worker B will skip it and look for the next available one.
  SELECT id INTO next_task_id
  FROM pipeline_tasks
  WHERE status = 'pending'
  ORDER BY created_at ASC
  FOR UPDATE SKIP LOCKED
  LIMIT 1;

  -- 2. If a task was found, mark it as claimed immediately.
  IF next_task_id IS NOT NULL THEN
    UPDATE pipeline_tasks
    SET 
        status = 'claimed',
        claimed_at = timezone('utc', now()),
        claimed_by = worker_val
    WHERE id = next_task_id;

    -- Return the claimed record
    RETURN QUERY SELECT * FROM pipeline_tasks WHERE id = next_task_id;
  END IF;
END;
$$ LANGUAGE plpgsql;
