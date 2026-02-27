-- ============================================================================
-- P1-2: AI Action Outcome Tracking Table
-- Tracks the effectiveness of proactive AI actions (notifications, reminders)
-- so we can measure whether AI interventions actually produce results.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.ai_action_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_type TEXT NOT NULL,
    target_id UUID,
    target_name TEXT,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    org_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL,
    action_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expected_outcome TEXT,
    actual_outcome TEXT,
    success BOOLEAN,
    measured_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_action_outcomes_unmeasured
    ON public.ai_action_outcomes(action_at)
    WHERE success IS NULL;
CREATE INDEX IF NOT EXISTS idx_ai_action_outcomes_type
    ON public.ai_action_outcomes(action_type, action_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_action_outcomes_user
    ON public.ai_action_outcomes(user_id, action_at DESC);

ALTER TABLE public.ai_action_outcomes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users view own action outcomes" ON public.ai_action_outcomes;
CREATE POLICY "Users view own action outcomes"
    ON public.ai_action_outcomes
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());
