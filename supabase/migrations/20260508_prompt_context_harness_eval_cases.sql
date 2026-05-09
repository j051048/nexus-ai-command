CREATE TABLE IF NOT EXISTS public.agent_eval_cases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    source_type text NOT NULL,
    source_ref text NOT NULL,
    status text NOT NULL DEFAULT 'pending_label',
    dimension text NOT NULL DEFAULT 'task_completion',
    input_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    expected_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_type, source_ref)
);

CREATE INDEX IF NOT EXISTS idx_agent_eval_cases_org_status
    ON public.agent_eval_cases(organization_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_eval_cases_dimension
    ON public.agent_eval_cases(dimension, status);

ALTER TABLE public.agent_eval_cases ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "org_members_view_agent_eval_cases" ON public.agent_eval_cases;
CREATE POLICY "org_members_view_agent_eval_cases"
ON public.agent_eval_cases
FOR SELECT
USING (
    organization_id IS NULL
    OR organization_id = public.get_user_org_id(auth.uid())
);

DROP POLICY IF EXISTS "org_admins_manage_agent_eval_cases" ON public.agent_eval_cases;
CREATE POLICY "org_admins_manage_agent_eval_cases"
ON public.agent_eval_cases
FOR ALL
USING (
    organization_id IS NULL
    OR (
        organization_id = public.get_user_org_id(auth.uid())
        AND EXISTS (
            SELECT 1 FROM public.users u
            WHERE u.id = auth.uid()
              AND u.role IN ('admin', 'founder', 'boss')
        )
    )
)
WITH CHECK (
    organization_id IS NULL
    OR (
        organization_id = public.get_user_org_id(auth.uid())
        AND EXISTS (
            SELECT 1 FROM public.users u
            WHERE u.id = auth.uid()
              AND u.role IN ('admin', 'founder', 'boss')
        )
    )
);
