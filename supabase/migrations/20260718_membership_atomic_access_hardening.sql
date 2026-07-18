-- Harden direct membership changes for concurrent administrators and trials.
--
-- Keep this as a follow-up migration instead of rewriting the original RPC
-- migration: deployed databases must receive the strengthened definition too.

CREATE OR REPLACE FUNCTION public.set_subscription_access_atomic(
  p_change_id UUID,
  p_org_id TEXT,
  p_plan TEXT,
  p_status TEXT,
  p_current_period_end TIMESTAMPTZ,
  p_access_source TEXT,
  p_admin_user_id TEXT,
  p_reason TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  existing_change public.subscription_access_versions%ROWTYPE;
  previous_snapshot JSONB;
  next_snapshot JSONB;
BEGIN
  IF p_plan NOT IN ('free', 'starter', 'professional', 'enterprise') THEN
    RAISE EXCEPTION 'Invalid subscription plan';
  END IF;
  IF p_status NOT IN ('active', 'inactive', 'trialing') THEN
    RAISE EXCEPTION 'Invalid subscription status';
  END IF;
  IF length(trim(coalesce(p_reason, ''))) < 2 THEN
    RAISE EXCEPTION 'A reason is required';
  END IF;

  -- Every entitlement writer uses the same organization-scoped lock. It
  -- prevents two admins (or a request approval and a direct override) from
  -- recording snapshots against stale state. The second lock serializes
  -- identical idempotency keys before their ledger lookup.
  PERFORM pg_advisory_xact_lock(
    hashtextextended('subscription:' || p_org_id, 0)
  );
  PERFORM pg_advisory_xact_lock(
    hashtextextended('subscription-change:' || p_change_id::TEXT, 0)
  );

  next_snapshot := jsonb_build_object(
    'plan', p_plan,
    'status', p_status,
    'current_period_end', p_current_period_end,
    'access_source', coalesce(nullif(p_access_source, ''), 'admin_override')
  );

  SELECT * INTO existing_change
  FROM public.subscription_access_versions
  WHERE id = p_change_id
  FOR UPDATE;

  IF FOUND THEN
    IF existing_change.org_id IS DISTINCT FROM p_org_id
       OR existing_change.next_snapshot IS DISTINCT FROM next_snapshot
       OR existing_change.created_by IS DISTINCT FROM p_admin_user_id
       OR existing_change.reason IS DISTINCT FROM p_reason THEN
      RAISE EXCEPTION 'Idempotency key was reused with a different payload';
    END IF;
    IF existing_change.change_status <> 'applied' THEN
      RAISE EXCEPTION 'Existing access change is not in an applied state';
    END IF;
    RETURN jsonb_build_object(
      'change_id', p_change_id,
      'org_id', p_org_id,
      'status', 'applied',
      'subscription', existing_change.next_snapshot,
      'replayed', TRUE
    );
  END IF;

  SELECT to_jsonb(subscription_row) INTO previous_snapshot
  FROM public.subscriptions subscription_row
  WHERE subscription_row.org_id = p_org_id;

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
    p_org_id,
    p_plan,
    p_status,
    p_current_period_end,
    coalesce(nullif(p_access_source, ''), 'admin_override'),
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
    plan = p_plan,
    tier = p_plan,
    updated_at = now()
  WHERE id::TEXT = p_org_id;

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
    created_at,
    updated_at
  ) VALUES (
    p_change_id,
    p_org_id,
    'direct',
    'applied',
    previous_snapshot,
    next_snapshot,
    p_reason,
    now(),
    now(),
    p_admin_user_id,
    p_admin_user_id,
    now(),
    now()
  );

  RETURN jsonb_build_object(
    'change_id', p_change_id,
    'org_id', p_org_id,
    'status', 'applied',
    'subscription', next_snapshot,
    'replayed', FALSE
  );
END;
$$;

REVOKE ALL ON FUNCTION public.set_subscription_access_atomic(
  UUID, TEXT, TEXT, TEXT, TIMESTAMPTZ, TEXT, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.set_subscription_access_atomic(
  UUID, TEXT, TEXT, TEXT, TIMESTAMPTZ, TEXT, TEXT, TEXT
) TO service_role;

COMMENT ON FUNCTION public.set_subscription_access_atomic(
  UUID, TEXT, TEXT, TEXT, TIMESTAMPTZ, TEXT, TEXT, TEXT
) IS 'Atomically applies one organization entitlement with organization and idempotency-key serialization.';
