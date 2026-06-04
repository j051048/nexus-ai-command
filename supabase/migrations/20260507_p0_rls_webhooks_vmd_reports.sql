-- P0 security baseline: close known RLS gaps for webhook and VMD report data.

CREATE TABLE IF NOT EXISTS public.webhook_subscriptions (
  id text PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  url text NOT NULL,
  events text[] NOT NULL DEFAULT ARRAY['*']::text[],
  secret_hash text NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  description text DEFAULT '',
  failure_count integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- If the table already existed with an older shape, make the migration
-- additive instead of relying on CREATE TABLE IF NOT EXISTS.
ALTER TABLE public.webhook_subscriptions
  ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS url text,
  ADD COLUMN IF NOT EXISTS events text[] NOT NULL DEFAULT ARRAY['*']::text[],
  ADD COLUMN IF NOT EXISTS secret_hash text,
  ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS description text DEFAULT '',
  ADD COLUMN IF NOT EXISTS failure_count integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_org
  ON public.webhook_subscriptions(organization_id, is_active);

CREATE TABLE IF NOT EXISTS public.webhook_delivery_log (
  id text PRIMARY KEY,
  subscription_id text REFERENCES public.webhook_subscriptions(id) ON DELETE CASCADE,
  organization_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  event text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending',
  attempts integer NOT NULL DEFAULT 0,
  response_code integer,
  response_body text,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.webhook_delivery_log
  ADD COLUMN IF NOT EXISTS subscription_id text REFERENCES public.webhook_subscriptions(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS event text,
  ADD COLUMN IF NOT EXISTS payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS attempts integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS response_code integer,
  ADD COLUMN IF NOT EXISTS response_body text,
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_webhook_delivery_log_org
  ON public.webhook_delivery_log(organization_id, created_at DESC);

ALTER TABLE public.vmd_reports
  ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id) ON DELETE SET NULL;

UPDATE public.vmd_reports
SET organization_id = tenant_id
WHERE organization_id IS NULL AND tenant_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_vmd_reports_organization_id
  ON public.vmd_reports(organization_id, report_type, report_date);

ALTER TABLE public.webhook_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webhook_delivery_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vmd_reports ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS webhook_subscriptions_org_select ON public.webhook_subscriptions;
CREATE POLICY webhook_subscriptions_org_select ON public.webhook_subscriptions
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS webhook_subscriptions_org_insert ON public.webhook_subscriptions;
CREATE POLICY webhook_subscriptions_org_insert ON public.webhook_subscriptions
  FOR INSERT TO authenticated
  WITH CHECK (organization_id = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS webhook_subscriptions_org_update ON public.webhook_subscriptions;
CREATE POLICY webhook_subscriptions_org_update ON public.webhook_subscriptions
  FOR UPDATE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()))
  WITH CHECK (organization_id = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS webhook_subscriptions_org_delete ON public.webhook_subscriptions;
CREATE POLICY webhook_subscriptions_org_delete ON public.webhook_subscriptions
  FOR DELETE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS webhook_delivery_log_org_select ON public.webhook_delivery_log;
CREATE POLICY webhook_delivery_log_org_select ON public.webhook_delivery_log
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS webhook_delivery_log_service_insert ON public.webhook_delivery_log;
CREATE POLICY webhook_delivery_log_service_insert ON public.webhook_delivery_log
  FOR INSERT TO service_role
  WITH CHECK (true);

DROP POLICY IF EXISTS vmd_reports_org_select ON public.vmd_reports;
CREATE POLICY vmd_reports_org_select ON public.vmd_reports
  FOR SELECT TO authenticated
  USING (COALESCE(organization_id, tenant_id) = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS vmd_reports_org_insert ON public.vmd_reports;
CREATE POLICY vmd_reports_org_insert ON public.vmd_reports
  FOR INSERT TO authenticated
  WITH CHECK (COALESCE(organization_id, tenant_id) = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS vmd_reports_org_update ON public.vmd_reports;
CREATE POLICY vmd_reports_org_update ON public.vmd_reports
  FOR UPDATE TO authenticated
  USING (COALESCE(organization_id, tenant_id) = public.get_user_org_id(auth.uid()))
  WITH CHECK (COALESCE(organization_id, tenant_id) = public.get_user_org_id(auth.uid()));
