-- Fix notifications table column names to match application code
-- Background: code uses "content" (20+ places), "is_read", "action_url"
-- but table was defined with "message" and no action_url column.
-- Note: "read" → "is_read" was already done previously.

-- 1. Rename "message" → "content" (matches all tool insert code)
ALTER TABLE public.notifications RENAME COLUMN message TO content;

-- 2. Add action_url column (used by notification_center_service + frontend)
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS action_url TEXT;
