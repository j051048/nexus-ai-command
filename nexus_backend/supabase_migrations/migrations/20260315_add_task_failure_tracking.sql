-- Add failure tracking columns to user_scheduled_tasks
ALTER TABLE user_scheduled_tasks
  ADD COLUMN IF NOT EXISTS consecutive_failures INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_error TEXT;

UPDATE user_scheduled_tasks SET consecutive_failures = 0 WHERE consecutive_failures IS NULL;
