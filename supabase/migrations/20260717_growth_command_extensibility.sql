-- Growth command center extension points and outcome evidence.
-- The current workspace reads existing CRM/VMD/tender tables; these tables
-- hold future connector state and auditable outcome events only.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.growth_signal_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    provider_key text NOT NULL,
    display_name text NOT NULL,
    status text NOT NULL DEFAULT 'disabled' CHECK (status IN ('disabled', 'active', 'degraded')),
    config jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_cursor text,
    last_synced_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, provider_key)
);

CREATE TABLE IF NOT EXISTS public.growth_playbook_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    playbook_key text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    overrides jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, playbook_key)
);

CREATE TABLE IF NOT EXISTS public.growth_outcome_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    user_id uuid,
    action_id text NOT NULL,
    outcome_type text NOT NULL CHECK (outcome_type IN ('qualified_lead', 'meeting', 'proposal', 'tender_submitted', 'won', 'lost', 'revenue', 'time_saved')),
    amount numeric(18, 2),
    currency text,
    evidence_ref text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_growth_signal_sources_org ON public.growth_signal_sources (organization_id, status);
CREATE INDEX IF NOT EXISTS idx_growth_playbooks_org ON public.growth_playbook_assignments (organization_id, enabled);
CREATE INDEX IF NOT EXISTS idx_growth_outcomes_org_time ON public.growth_outcome_events (organization_id, occurred_at DESC);

ALTER TABLE public.growth_signal_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.growth_playbook_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.growth_outcome_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS growth_signal_sources_tenant_isolation ON public.growth_signal_sources;
CREATE POLICY growth_signal_sources_tenant_isolation ON public.growth_signal_sources
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

DROP POLICY IF EXISTS growth_playbook_assignments_tenant_isolation ON public.growth_playbook_assignments;
CREATE POLICY growth_playbook_assignments_tenant_isolation ON public.growth_playbook_assignments
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

DROP POLICY IF EXISTS growth_outcome_events_tenant_isolation ON public.growth_outcome_events;
CREATE POLICY growth_outcome_events_tenant_isolation ON public.growth_outcome_events
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
