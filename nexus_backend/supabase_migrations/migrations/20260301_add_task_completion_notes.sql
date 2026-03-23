-- Add completion_notes and completed_at columns to oa_tasks
-- Allows users to add notes when completing a task

ALTER TABLE public.oa_tasks ADD COLUMN IF NOT EXISTS completion_notes TEXT;
ALTER TABLE public.oa_tasks ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
