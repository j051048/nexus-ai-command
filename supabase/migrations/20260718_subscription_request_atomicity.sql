-- Finish subscription request approval inside one database transaction.
-- The previous application flow updated organizations and the access-version
-- ledger after the RPC, which allowed partial entitlement state on failure.

CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_access_versions_request
  ON public.subscription_access_versions (request_id)
  WHERE request_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.resolve_subscription_access_request(
  p_request_id UUID,
  p_decision TEXT,
  p_reviewed_by TEXT,
  p_reason TEXT,
  p_plan TEXT DEFAULT NULL,
  p_expires_at TIMESTAMPTZ DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  request_row public.subscription_access_requests%ROWTYPE;
  existing_change public.subscription_access_versions%ROWTYPE;
  effective_plan TEXT;
  effective_expiry TIMESTAMPTZ;
  previous_snapshot JSONB;
  next_snapshot JSONB;
  change_id UUID := gen_random_uuid();
BEGIN
  IF p_decision NOT IN ('approved', 'rejected') THEN
    RAISE EXCEPTION 'Invalid subscription decision';
  END IF;
  IF length(trim(coalesce(p_reason, ''))) < 2 THEN
    RAISE EXCEPTION 'A review reason is required';
  END IF;

  SELECT * INTO request_row
  FROM public.subscription_access_requests
  WHERE id = p_request_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Subscription request not found';
  END IF;

  -- Coordinate with direct membership overrides so both paths observe and
  -- version one organization entitlement in a deterministic order.
  PERFORM pg_advisory_xact_lock(
    hashtextextended('subscription:' || request_row.org_id, 0)
  );

  IF request_row.status <> 'pending' THEN
    IF request_row.status <> p_decision THEN
      RAISE EXCEPTION 'Subscription request has already been reviewed differently';
    END IF;
    SELECT * INTO existing_change
    FROM public.subscription_access_versions
    WHERE request_id = p_request_id;
    RETURN jsonb_build_object(
      'request_id', p_request_id,
      'change_id', existing_change.id,
      'org_id', request_row.org_id,
      'status', request_row.status,
      'plan', CASE WHEN request_row.status = 'approved'
        THEN existing_change.next_snapshot->>'plan' ELSE NULL END,
      'current_period_end', request_row.approved_expires_at,
      'replayed', TRUE
    );
  END IF;

  effective_plan := coalesce(p_plan, request_row.requested_plan);
  effective_expiry := coalesce(
    p_expires_at,
    now() + make_interval(days => request_row.requested_days)
  );

  IF p_decision = 'approved' THEN
    IF effective_plan NOT IN ('starter', 'professional', 'enterprise') THEN
      RAISE EXCEPTION 'Invalid approved plan';
    END IF;
    IF effective_expiry <= now() THEN
      RAISE EXCEPTION 'Expiry date must be in the future';
    END IF;

    SELECT to_jsonb(subscription_row) INTO previous_snapshot
    FROM public.subscriptions subscription_row
    WHERE subscription_row.org_id = request_row.org_id;

    next_snapshot := jsonb_build_object(
      'plan', effective_plan,
      'status', 'active',
      'current_period_end', effective_expiry,
      'access_source', 'admin_approved'
    );

    INSERT INTO public.subscriptions (
      org_id, plan, status, current_period_end, access_source,
      approved_by, approved_at, notes, updated_at
    ) VALUES (
      request_row.org_id, effective_plan, 'active', effective_expiry,
      'admin_approved', p_reviewed_by, now(), p_reason, now()
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
      plan = effective_plan,
      tier = effective_plan,
      updated_at = now()
    WHERE id::TEXT = request_row.org_id;

    INSERT INTO public.subscription_access_versions (
      id, org_id, request_id, change_kind, change_status,
      previous_snapshot, next_snapshot, reason, effective_at, applied_at,
      created_by, applied_by, created_at, updated_at
    ) VALUES (
      change_id, request_row.org_id, p_request_id, 'request', 'applied',
      previous_snapshot, next_snapshot, p_reason, now(), now(),
      p_reviewed_by, p_reviewed_by, now(), now()
    );
  ELSE
    change_id := NULL;
  END IF;

  UPDATE public.subscription_access_requests SET
    status = p_decision,
    reviewed_by = p_reviewed_by,
    reviewed_at = now(),
    review_reason = p_reason,
    approved_expires_at = CASE WHEN p_decision = 'approved' THEN effective_expiry ELSE NULL END,
    updated_at = now()
  WHERE id = p_request_id;

  RETURN jsonb_build_object(
    'request_id', p_request_id,
    'change_id', change_id,
    'org_id', request_row.org_id,
    'status', p_decision,
    'plan', CASE WHEN p_decision = 'approved' THEN effective_plan ELSE NULL END,
    'current_period_end', CASE WHEN p_decision = 'approved' THEN effective_expiry ELSE NULL END,
    'replayed', FALSE
  );
END;
$$;

REVOKE ALL ON FUNCTION public.resolve_subscription_access_request(
  UUID, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.resolve_subscription_access_request(
  UUID, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) TO service_role;

COMMENT ON FUNCTION public.resolve_subscription_access_request(
  UUID, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) IS 'Atomically resolves one membership request, entitlement, organization projection and rollback evidence.';
