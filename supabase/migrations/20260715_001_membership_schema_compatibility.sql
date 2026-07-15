-- Converge scheduled membership functions with the canonical organizations
-- schema. Membership lifecycle lives in subscriptions; organizations only
-- mirrors plan/tier for compatibility with legacy reads.

-- Earlier provider/trial flows inserted one row per change because org_id had
-- no uniqueness contract. Keep the strongest currently valid entitlement,
-- then the latest record, before enforcing one row per organization. Preserve
-- discarded rows in the existing access-version ledger for auditability.
WITH ranked_subscriptions AS (
  SELECT
    subscriptions.*,
    row_number() OVER (
      PARTITION BY org_id
      ORDER BY
        CASE
          WHEN plan <> 'free'
            AND status IN ('active', 'trialing')
            AND (current_period_end IS NULL OR current_period_end > now())
          THEN 1
          ELSE 0
        END DESC,
        coalesce(approved_at, updated_at, created_at) DESC,
        id DESC
    ) AS row_rank
  FROM public.subscriptions subscriptions
)
INSERT INTO public.subscription_access_versions (
  org_id,
  change_kind,
  change_status,
  next_snapshot,
  reason,
  effective_at,
  applied_at,
  created_by,
  applied_by,
  created_at,
  updated_at
)
SELECT
  org_id,
  'direct',
  'applied',
  to_jsonb(ranked_subscriptions) - 'row_rank',
  'Archived duplicate subscription during membership schema convergence',
  coalesce(approved_at, updated_at, created_at, now()),
  coalesce(approved_at, updated_at, created_at, now()),
  'schema_migration',
  'schema_migration',
  coalesce(created_at, now()),
  now()
FROM ranked_subscriptions
WHERE row_rank > 1;

WITH ranked_subscriptions AS (
  SELECT
    id,
    row_number() OVER (
      PARTITION BY org_id
      ORDER BY
        CASE
          WHEN plan <> 'free'
            AND status IN ('active', 'trialing')
            AND (current_period_end IS NULL OR current_period_end > now())
          THEN 1
          ELSE 0
        END DESC,
        coalesce(approved_at, updated_at, created_at) DESC,
        id DESC
    ) AS row_rank
  FROM public.subscriptions
)
DELETE FROM public.subscriptions subscriptions
USING ranked_subscriptions ranked
WHERE subscriptions.id = ranked.id
  AND ranked.row_rank > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_org_id
  ON public.subscriptions (org_id);

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
    updated_at = now()
  WHERE id::TEXT = source_row.org_id;

  INSERT INTO public.subscription_access_versions (
    id,
    org_id,
    change_kind,
    change_status,
    previous_snapshot,
    next_snapshot,
    reason,
    effective_at,
    applied_at,
    created_by,
    applied_by,
    rollback_of
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

REVOKE ALL ON FUNCTION public.apply_subscription_access_change(UUID, TEXT)
  FROM PUBLIC;
REVOKE ALL ON FUNCTION public.rollback_subscription_access_change(UUID, TEXT, TEXT)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.apply_subscription_access_change(UUID, TEXT)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.rollback_subscription_access_change(UUID, TEXT, TEXT)
  TO service_role;

COMMENT ON FUNCTION public.apply_subscription_access_change(UUID, TEXT) IS
  'Atomically applies a scheduled enterprise membership without legacy organization status columns.';
COMMENT ON FUNCTION public.rollback_subscription_access_change(UUID, TEXT, TEXT) IS
  'Restores a prior enterprise membership without legacy organization status columns.';
