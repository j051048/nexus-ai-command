-- P0/P1 action-first workspace audit trail.
-- Records user feedback and completion signals from the unified action inbox.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.action_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    user_id uuid,
    action_id text NOT NULL,
    source text NOT NULL CHECK (source IN ('approval', 'notification', 'crm', 'system')),
    source_id text,
    event_type text NOT NULL CHECK (
        event_type IN (
            'viewed',
            'accepted',
            'completed',
            'ignored',
            'snoozed',
            'command_executed'
        )
    ),
    status text NOT NULL DEFAULT 'recorded',
    comment text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_action_events_org_created
    ON public.action_events (organization_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_action_events_action_created
    ON public.action_events (action_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_action_events_source
    ON public.action_events (source, event_type, created_at DESC);

ALTER TABLE public.action_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p0_action_events_tenant_isolation ON public.action_events;
CREATE POLICY p0_action_events_tenant_isolation
    ON public.action_events
    FOR ALL
    USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
