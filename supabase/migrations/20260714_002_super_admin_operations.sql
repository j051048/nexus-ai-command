-- Super-admin operating foundation: access versioning, commercial ledger,
-- scoped platform roles, scheduled changes, and realtime entitlement updates.

ALTER TABLE public.subscription_access_requests
  ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
  ADD COLUMN IF NOT EXISTS due_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS request_kind TEXT NOT NULL DEFAULT 'activation'
    CHECK (request_kind IN ('activation', 'renewal', 'plan_change', 'trial'));

UPDATE public.subscription_access_requests
SET due_at = created_at + INTERVAL '24 hours'
WHERE due_at IS NULL;

CREATE TABLE IF NOT EXISTS public.platform_admin_assignments (
  user_id TEXT PRIMARY KEY,
  admin_role TEXT NOT NULL CHECK (
    admin_role IN (
      'platform_owner',
      'billing_operator',
      'support_operator',
      'security_auditor',
      'finance_reviewer'
    )
  ),
  permissions JSONB NOT NULL DEFAULT '[]'::JSONB,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.subscription_commercial_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id TEXT NOT NULL,
  order_number TEXT NOT NULL UNIQUE,
  contract_number TEXT,
  amount_cents BIGINT NOT NULL DEFAULT 0 CHECK (amount_cents >= 0),
  discount_cents BIGINT NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
  currency TEXT NOT NULL DEFAULT 'CNY',
  payment_status TEXT NOT NULL DEFAULT 'pending' CHECK (
    payment_status IN ('pending', 'partial', 'paid', 'overdue', 'waived', 'refunded')
  ),
  paid_at TIMESTAMPTZ,
  due_at TIMESTAMPTZ,
  invoice_status TEXT NOT NULL DEFAULT 'none' CHECK (
    invoice_status IN ('none', 'requested', 'issued', 'cancelled')
  ),
  invoice_number TEXT,
  sales_owner TEXT,
  gifted_days INTEGER NOT NULL DEFAULT 0 CHECK (gifted_days BETWEEN 0 AND 3650),
  evidence_url TEXT,
  notes TEXT,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscription_commercial_org_created
  ON public.subscription_commercial_records (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_subscription_commercial_payment_due
  ON public.subscription_commercial_records (payment_status, due_at);

CREATE TABLE IF NOT EXISTS public.subscription_access_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id TEXT NOT NULL,
  request_id UUID,
  commercial_record_id UUID,
  change_kind TEXT NOT NULL DEFAULT 'direct' CHECK (
    change_kind IN ('direct', 'request', 'scheduled', 'rollback', 'expiry')
  ),
  change_status TEXT NOT NULL DEFAULT 'scheduled' CHECK (
    change_status IN ('scheduled', 'applied', 'cancelled', 'rolled_back', 'failed')
  ),
  previous_snapshot JSONB,
  next_snapshot JSONB NOT NULL,
  reason TEXT NOT NULL,
  effective_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  applied_at TIMESTAMPTZ,
  created_by TEXT NOT NULL,
  applied_by TEXT,
  rollback_of UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscription_access_versions_org_created
  ON public.subscription_access_versions (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_subscription_access_versions_due
  ON public.subscription_access_versions (change_status, effective_at)
  WHERE change_status = 'scheduled';

ALTER TABLE public.platform_admin_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscription_commercial_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscription_access_versions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS platform_admin_assignments_service_only
  ON public.platform_admin_assignments;
CREATE POLICY platform_admin_assignments_service_only
  ON public.platform_admin_assignments
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS subscription_commercial_records_service_only
  ON public.subscription_commercial_records;
CREATE POLICY subscription_commercial_records_service_only
  ON public.subscription_commercial_records
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS subscription_access_versions_service_only
  ON public.subscription_access_versions;
CREATE POLICY subscription_access_versions_service_only
  ON public.subscription_access_versions
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE OR REPLACE FUNCTION public.apply_subscription_access_change(
  p_change_id UUID,
  p_applied_by TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  change_row public.subscription_access_versions%ROWTYPE;
  current_snapshot JSONB;
  applied_snapshot JSONB;
BEGIN
  SELECT * INTO change_row
  FROM public.subscription_access_versions
  WHERE id = p_change_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Access change not found';
  END IF;
  IF change_row.change_status <> 'scheduled' THEN
    RAISE EXCEPTION 'Access change is not scheduled';
  END IF;
  IF change_row.effective_at > now() THEN
    RAISE EXCEPTION 'Access change is not due';
  END IF;

  SELECT to_jsonb(s) INTO current_snapshot
  FROM public.subscriptions s
  WHERE s.org_id = change_row.org_id;

  applied_snapshot := change_row.next_snapshot;
  INSERT INTO public.subscriptions (
    org_id,
    plan,
    status,
    current_period_end,
    access_source,
    approved_by,
    approved_at,
    notes,
    updated_at
  ) VALUES (
    change_row.org_id,
    applied_snapshot->>'plan',
    coalesce(applied_snapshot->>'status', 'active'),
    nullif(applied_snapshot->>'current_period_end', '')::TIMESTAMPTZ,
    coalesce(applied_snapshot->>'access_source', 'admin_override'),
    p_applied_by,
    now(),
    change_row.reason,
    now()
  )
  ON CONFLICT (org_id) DO UPDATE SET
    plan = EXCLUDED.plan,
    status = EXCLUDED.status,
    current_period_end = EXCLUDED.current_period_end,
    access_source = EXCLUDED.access_source,
    approved_by = EXCLUDED.approved_by,
    approved_at = EXCLUDED.approved_at,
    notes = EXCLUDED.notes,
    updated_at = EXCLUDED.updated_at;

  UPDATE public.organizations SET
    plan = applied_snapshot->>'plan',
    tier = applied_snapshot->>'plan',
    subscription_status = coalesce(applied_snapshot->>'status', 'active'),
    updated_at = now()
  WHERE id::TEXT = change_row.org_id;

  UPDATE public.subscription_access_versions SET
    previous_snapshot = current_snapshot,
    change_status = 'applied',
    applied_at = now(),
    applied_by = p_applied_by,
    updated_at = now()
  WHERE id = p_change_id;

  RETURN jsonb_build_object(
    'change_id', p_change_id,
    'org_id', change_row.org_id,
    'status', 'applied',
    'subscription', applied_snapshot
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.rollback_subscription_access_change(
  p_change_id UUID,
  p_admin_user_id TEXT,
  p_reason TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  source_row public.subscription_access_versions%ROWTYPE;
  current_snapshot JSONB;
  restore_snapshot JSONB;
  rollback_id UUID := gen_random_uuid();
BEGIN
  IF length(trim(coalesce(p_reason, ''))) < 2 THEN
    RAISE EXCEPTION 'A rollback reason is required';
  END IF;

  SELECT * INTO source_row
  FROM public.subscription_access_versions
  WHERE id = p_change_id
  FOR UPDATE;

  IF NOT FOUND OR source_row.change_status <> 'applied' THEN
    RAISE EXCEPTION 'Applied access change not found';
  END IF;

  SELECT to_jsonb(s) INTO current_snapshot
  FROM public.subscriptions s
  WHERE s.org_id = source_row.org_id;

  restore_snapshot := coalesce(
    source_row.previous_snapshot,
    jsonb_build_object(
      'plan', 'free',
      'status', 'inactive',
      'current_period_end', NULL,
      'access_source', 'admin_override'
    )
  );

  INSERT INTO public.subscriptions (
    org_id, plan, status, current_period_end, access_source,
    approved_by, approved_at, notes, updated_at
  ) VALUES (
    source_row.org_id,
    restore_snapshot->>'plan',
    coalesce(restore_snapshot->>'status', 'inactive'),
    nullif(restore_snapshot->>'current_period_end', '')::TIMESTAMPTZ,
    'admin_override',
    p_admin_user_id,
    now(),
    p_reason,
    now()
  )
  ON CONFLICT (org_id) DO UPDATE SET
    plan = EXCLUDED.plan,
    status = EXCLUDED.status,
    current_period_end = EXCLUDED.current_period_end,
    access_source = EXCLUDED.access_source,
    approved_by = EXCLUDED.approved_by,
    approved_at = EXCLUDED.approved_at,
    notes = EXCLUDED.notes,
    updated_at = EXCLUDED.updated_at;

  UPDATE public.organizations SET
    plan = restore_snapshot->>'plan',
    tier = restore_snapshot->>'plan',
    subscription_status = coalesce(restore_snapshot->>'status', 'inactive'),
    updated_at = now()
  WHERE id::TEXT = source_row.org_id;

  INSERT INTO public.subscription_access_versions (
    id, org_id, change_kind, change_status, previous_snapshot,
    next_snapshot, reason, effective_at, applied_at, created_by,
    applied_by, rollback_of
  ) VALUES (
    rollback_id,
    source_row.org_id,
    'rollback',
    'applied',
    current_snapshot,
    restore_snapshot,
    p_reason,
    now(),
    now(),
    p_admin_user_id,
    p_admin_user_id,
    source_row.id
  );

  UPDATE public.subscription_access_versions SET
    change_status = 'rolled_back',
    updated_at = now()
  WHERE id = source_row.id;

  RETURN jsonb_build_object(
    'change_id', rollback_id,
    'rolled_back_change_id', source_row.id,
    'org_id', source_row.org_id,
    'subscription', restore_snapshot
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.apply_due_subscription_access_changes()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  due_change RECORD;
  applied_count INTEGER := 0;
BEGIN
  FOR due_change IN
    SELECT id, created_by
    FROM public.subscription_access_versions
    WHERE change_status = 'scheduled'
      AND effective_at <= now()
    ORDER BY effective_at
    FOR UPDATE SKIP LOCKED
  LOOP
    PERFORM public.apply_subscription_access_change(
      due_change.id,
      due_change.created_by
    );
    applied_count := applied_count + 1;
  END LOOP;
  RETURN applied_count;
END;
$$;

REVOKE ALL ON FUNCTION public.apply_subscription_access_change(UUID, TEXT)
  FROM PUBLIC;
REVOKE ALL ON FUNCTION public.rollback_subscription_access_change(UUID, TEXT, TEXT)
  FROM PUBLIC;
REVOKE ALL ON FUNCTION public.apply_due_subscription_access_changes()
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.apply_subscription_access_change(UUID, TEXT)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.rollback_subscription_access_change(UUID, TEXT, TEXT)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.apply_due_subscription_access_changes()
  TO service_role;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime')
     AND NOT EXISTS (
       SELECT 1 FROM pg_publication_tables
       WHERE pubname = 'supabase_realtime'
         AND schemaname = 'public'
         AND tablename = 'subscriptions'
     ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.subscriptions;
  END IF;
END
$$;

COMMENT ON TABLE public.subscription_access_versions IS
  'Immutable membership change timeline with scheduled application and rollback snapshots.';
COMMENT ON TABLE public.subscription_commercial_records IS
  'Commercial evidence for manually approved membership access; separate from entitlement state.';
COMMENT ON TABLE public.platform_admin_assignments IS
  'Scoped duties for platform super-admin operators.';
