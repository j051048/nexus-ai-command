-- ============================================================================
-- Migration: Create user_scheduled_tasks table for user-defined scheduled tasks
-- Date: 2026-02-26
-- Purpose: Allow users to create custom scheduled tasks via AI conversation.
--          e.g. "每天下午4点提醒我检查客户回复"
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.user_scheduled_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL,
    -- Task definition
    name TEXT NOT NULL,
    prompt TEXT NOT NULL,                   -- The AI prompt to execute
    schedule_type TEXT NOT NULL DEFAULT 'daily',  -- daily, weekly, once, interval
    -- Schedule parameters (cron-like)
    hour INTEGER CHECK (hour >= 0 AND hour <= 23),
    minute INTEGER DEFAULT 0 CHECK (minute >= 0 AND minute <= 59),
    day_of_week INTEGER CHECK (day_of_week >= 0 AND day_of_week <= 6),  -- 0=Monday
    interval_minutes INTEGER CHECK (interval_minutes > 0),
    -- For one-time tasks
    execute_at TIMESTAMPTZ,
    -- Execution tracking
    is_active BOOLEAN DEFAULT TRUE,
    last_executed_at TIMESTAMPTZ,
    next_execution_at TIMESTAMPTZ,
    execution_count INTEGER DEFAULT 0,
    last_result TEXT,
    -- Notification
    notify_method TEXT DEFAULT 'notification',  -- notification, none
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_user_scheduled_tasks_user
    ON public.user_scheduled_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_scheduled_tasks_active
    ON public.user_scheduled_tasks(is_active, next_execution_at)
    WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_user_scheduled_tasks_org
    ON public.user_scheduled_tasks(organization_id);

-- RLS
ALTER TABLE public.user_scheduled_tasks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users manage own scheduled tasks" ON public.user_scheduled_tasks;
CREATE POLICY "Users manage own scheduled tasks"
    ON public.user_scheduled_tasks
    FOR ALL TO authenticated
    USING (user_id = auth.uid());

-- Auto-update trigger
CREATE OR REPLACE FUNCTION public.update_user_scheduled_tasks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_scheduled_tasks_updated ON public.user_scheduled_tasks;
CREATE TRIGGER trg_user_scheduled_tasks_updated
    BEFORE UPDATE ON public.user_scheduled_tasks
    FOR EACH ROW EXECUTE FUNCTION public.update_user_scheduled_tasks_updated_at();
