-- Migration: Remove unique constraint on thread_id to allow multiple applications per thread
-- This is necessary for a multi-user system where same sender might send different jobs.

DO $$
BEGIN
    -- Drop the unique index if it exists
    -- The error message indicated the name was idx_applications_thread_id
    DROP INDEX IF EXISTS idx_applications_thread_id;
    
    -- If it's a constraint rather than just an index
    ALTER TABLE applications DROP CONSTRAINT IF EXISTS applications_thread_id_key;
    
    -- Re-create it as a NON-UNIQUE index for performance
    CREATE INDEX IF NOT EXISTS idx_applications_thread_id ON applications(thread_id);
    
    RAISE NOTICE 'Removed unique constraint on applications(thread_id)';
END $$;
