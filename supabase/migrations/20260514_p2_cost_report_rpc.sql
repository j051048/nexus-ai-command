-- P2: Durable token usage attribution and cost report RPC.

CREATE TABLE IF NOT EXISTS public.user_token_usage (
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL,
  org_id uuid,
  date date NOT NULL DEFAULT CURRENT_DATE,
  total_tokens bigint NOT NULL DEFAULT 0,
  estimated_cost_usd numeric(12,6) NOT NULL DEFAULT 0,
  request_count integer NOT NULL DEFAULT 0,
  department_id uuid,
  project_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, date)
);

ALTER TABLE public.user_token_usage ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_user_token_usage_org_date
  ON public.user_token_usage(org_id, date DESC);

CREATE INDEX IF NOT EXISTS idx_user_token_usage_user_date
  ON public.user_token_usage(user_id, date DESC);

CREATE OR REPLACE FUNCTION public.upsert_daily_token_usage(
  p_user_id uuid,
  p_org_id uuid,
  p_date date,
  p_tokens bigint,
  p_cost numeric,
  p_department_id uuid DEFAULT NULL,
  p_project_id uuid DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.user_token_usage (
    user_id,
    org_id,
    date,
    total_tokens,
    estimated_cost_usd,
    request_count,
    department_id,
    project_id
  )
  VALUES (
    p_user_id,
    p_org_id,
    p_date,
    COALESCE(p_tokens, 0),
    COALESCE(p_cost, 0),
    1,
    p_department_id,
    p_project_id
  )
  ON CONFLICT (user_id, date)
  DO UPDATE SET
    org_id = COALESCE(EXCLUDED.org_id, public.user_token_usage.org_id),
    total_tokens = public.user_token_usage.total_tokens + EXCLUDED.total_tokens,
    estimated_cost_usd = public.user_token_usage.estimated_cost_usd + EXCLUDED.estimated_cost_usd,
    request_count = public.user_token_usage.request_count + 1,
    department_id = COALESCE(EXCLUDED.department_id, public.user_token_usage.department_id),
    project_id = COALESCE(EXCLUDED.project_id, public.user_token_usage.project_id),
    updated_at = now();
END;
$$;

CREATE OR REPLACE FUNCTION public.get_cost_report(
  p_org_id uuid,
  p_days integer DEFAULT 30
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH scoped AS (
    SELECT
      COALESCE(department_id::text, 'unassigned') AS department_id,
      COALESCE(project_id::text, 'unassigned') AS project_id,
      total_tokens,
      estimated_cost_usd
    FROM public.user_token_usage
    WHERE org_id = p_org_id
      AND date >= CURRENT_DATE - GREATEST(p_days, 1)
  ),
  dept AS (
    SELECT
      department_id,
      SUM(estimated_cost_usd)::numeric(12,6) AS cost_usd,
      SUM(total_tokens)::bigint AS tokens
    FROM scoped
    GROUP BY department_id
  ),
  project AS (
    SELECT
      project_id,
      SUM(estimated_cost_usd)::numeric(12,6) AS cost_usd,
      SUM(total_tokens)::bigint AS tokens
    FROM scoped
    GROUP BY project_id
  )
  SELECT jsonb_build_object(
    'by_department', COALESCE((SELECT jsonb_agg(to_jsonb(dept) ORDER BY cost_usd DESC) FROM dept), '[]'::jsonb),
    'by_project', COALESCE((SELECT jsonb_agg(to_jsonb(project) ORDER BY cost_usd DESC) FROM project), '[]'::jsonb),
    'by_model', '[]'::jsonb,
    'total_cost_usd', COALESCE((SELECT SUM(estimated_cost_usd) FROM scoped), 0),
    'total_tokens', COALESCE((SELECT SUM(total_tokens) FROM scoped), 0)
  );
$$;

GRANT EXECUTE ON FUNCTION public.upsert_daily_token_usage(uuid, uuid, date, bigint, numeric, uuid, uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.get_cost_report(uuid, integer) TO service_role;
