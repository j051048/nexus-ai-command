-- Converge legacy webhook tenant columns on the canonical organization_id.
-- Existing deployments may still have org_id from an earlier additive migration.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'webhook_subscriptions'
      AND column_name = 'org_id'
  ) THEN
    UPDATE public.webhook_subscriptions
    SET organization_id = org_id
    WHERE organization_id IS NULL;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'webhook_delivery_log'
      AND column_name = 'org_id'
  ) THEN
    UPDATE public.webhook_delivery_log
    SET organization_id = org_id
    WHERE organization_id IS NULL;
  END IF;
END
$$;

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

ALTER TABLE public.webhook_subscriptions
  DROP COLUMN IF EXISTS org_id;

ALTER TABLE public.webhook_delivery_log
  DROP COLUMN IF EXISTS org_id;
