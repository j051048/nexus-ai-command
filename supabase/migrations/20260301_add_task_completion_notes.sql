-- Add completion_notes column to oa_tasks for task completion workflow
-- Employees fill in completion notes when marking tasks as completed

ALTER TABLE public.oa_tasks ADD COLUMN IF NOT EXISTS completion_notes TEXT;
