ALTER TABLE public.ai_feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_feedback_org_select ON public.ai_feedback;
CREATE POLICY ai_feedback_org_select
ON public.ai_feedback
FOR SELECT TO authenticated
USING (tenant_id = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS ai_feedback_user_insert ON public.ai_feedback;
CREATE POLICY ai_feedback_user_insert
ON public.ai_feedback
FOR INSERT TO authenticated
WITH CHECK (
    user_id = auth.uid()
    AND (
        tenant_id IS NULL
        OR tenant_id = public.get_user_org_id(auth.uid())
    )
);

ALTER TABLE public.agent_eval_cases
    ADD COLUMN IF NOT EXISTS labelled_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS labelled_at timestamptz;
