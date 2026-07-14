-- Manual subscription approval workflow.
-- Billing access is granted by a platform super admin and subscriptions remains
-- the single source of truth consumed by the application.

ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS access_source TEXT NOT NULL DEFAULT 'self_service',
  ADD COLUMN IF NOT EXISTS approved_by TEXT,
  ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS notes TEXT;

CREATE TABLE IF NOT EXISTS public.subscription_access_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  requested_plan TEXT NOT NULL CHECK (
    requested_plan IN ('starter', 'professional', 'enterprise')
  ),
  requested_days INTEGER NOT NULL DEFAULT 365 CHECK (
    requested_days BETWEEN 1 AND 3650
  ),
  note TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (
    status IN ('pending', 'approved', 'rejected', 'cancelled')
  ),
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  review_reason TEXT,
  approved_expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_access_requests_pending_org
  ON public.subscription_access_requests (org_id)
  WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_subscription_access_requests_status_created
  ON public.subscription_access_requests (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_subscription_access_requests_org_created
  ON public.subscription_access_requests (org_id, created_at DESC);

ALTER TABLE public.subscription_access_requests ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'subscription_access_requests'
      AND policyname = 'subscription_requests_org_read'
  ) THEN
    CREATE POLICY subscription_requests_org_read
      ON public.subscription_access_requests
      FOR SELECT
      USING (org_id = get_user_org_id());
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'subscription_access_requests'
      AND policyname = 'subscription_requests_org_insert'
  ) THEN
    CREATE POLICY subscription_requests_org_insert
      ON public.subscription_access_requests
      FOR INSERT
      WITH CHECK (org_id = get_user_org_id());
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'subscription_access_requests'
      AND policyname = 'subscription_requests_org_cancel'
  ) THEN
    CREATE POLICY subscription_requests_org_cancel
      ON public.subscription_access_requests
      FOR UPDATE
      USING (org_id = get_user_org_id() AND status = 'pending')
      WITH CHECK (org_id = get_user_org_id() AND status = 'cancelled');
  END IF;
END
$$;

COMMENT ON TABLE public.subscription_access_requests IS
  'Manual plan activation and renewal requests reviewed by platform super admins.';

COMMENT ON COLUMN public.subscriptions.access_source IS
  'self_service, admin_approved, admin_override, or payment_provider';

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
  effective_plan TEXT;
  effective_expiry TIMESTAMPTZ;
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
  IF request_row.status <> 'pending' THEN
    RAISE EXCEPTION 'Subscription request has already been reviewed';
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
      request_row.org_id,
      effective_plan,
      'active',
      effective_expiry,
      'admin_approved',
      p_reviewed_by,
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
    'org_id', request_row.org_id,
    'status', p_decision,
    'plan', CASE WHEN p_decision = 'approved' THEN effective_plan ELSE NULL END,
    'current_period_end', CASE WHEN p_decision = 'approved' THEN effective_expiry ELSE NULL END
  );
END;
$$;

REVOKE ALL ON FUNCTION public.resolve_subscription_access_request(
  UUID, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.resolve_subscription_access_request(
  UUID, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) TO service_role;
