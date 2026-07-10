-- P0 runtime/schema convergence for LLM cost, quota and immutable audit data.

-- Canonical LLM call-log columns follow the original table contract used by
-- dashboard and scheduler queries.
ALTER TABLE IF EXISTS public.llm_call_log
  ADD COLUMN IF NOT EXISTS trace_id text;

CREATE INDEX IF NOT EXISTS idx_llm_call_log_trace_id
  ON public.llm_call_log(trace_id)
  WHERE trace_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.get_llm_cost_report(
  p_org_id uuid,
  p_start timestamptz,
  p_end timestamptz
)
RETURNS TABLE (
  model_code text,
  total_calls bigint,
  total_tokens bigint,
  total_cost_usd numeric,
  avg_duration_ms numeric
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    COALESCE(log.model_code, 'unknown')::text,
    COUNT(*)::bigint,
    COALESCE(SUM(log.total_tokens), 0)::bigint,
    COALESCE(SUM(log.call_cost), 0)::numeric,
    COALESCE(AVG(log.exec_time_ms), 0)::numeric
  FROM public.llm_call_log AS log
  WHERE log.tenant_id = p_org_id
    AND log.create_time >= p_start
    AND log.create_time < p_end
  GROUP BY COALESCE(log.model_code, 'unknown')
  ORDER BY COALESCE(SUM(log.call_cost), 0) DESC;
$$;

REVOKE ALL ON FUNCTION public.get_llm_cost_report(uuid, timestamptz, timestamptz)
  FROM public, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_llm_cost_report(uuid, timestamptz, timestamptz)
  TO service_role;

-- Canonical immutable audit schema. CREATE/ALTER keeps existing deployments
-- compatible while making fresh environments self-describing.
CREATE TABLE IF NOT EXISTS public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action text NOT NULL,
  actor_user_id uuid,
  org_id uuid,
  target_id text,
  target_table text,
  details_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  ip_address text,
  user_agent text,
  session_id text,
  request_id text,
  status text NOT NULL DEFAULT 'success',
  error_message text,
  timestamp timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS actor_user_id uuid;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS org_id uuid;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS target_id text;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS target_table text;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS details_json jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS session_id text;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS request_id text;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'success';
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS error_message text;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS timestamp timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_audit_logs_org_timestamp
  ON public.audit_logs(org_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_timestamp
  ON public.audit_logs(actor_user_id, timestamp DESC);

ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p0_audit_logs_tenant_isolation ON public.audit_logs;
CREATE POLICY p0_audit_logs_tenant_isolation ON public.audit_logs
  FOR ALL
  USING (org_id::text = public.current_tenant_id_text() OR auth.role() = 'service_role')
  WITH CHECK (org_id::text = public.current_tenant_id_text() OR auth.role() = 'service_role');

CREATE OR REPLACE FUNCTION public.prevent_audit_log_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'audit_logs is append-only: % operations are forbidden', TG_OP;
END;
$$;

DROP TRIGGER IF EXISTS audit_logs_immutable ON public.audit_logs;
CREATE TRIGGER audit_logs_immutable
  BEFORE UPDATE OR DELETE ON public.audit_logs
  FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_log_mutation();

-- Quota configuration uses daily/monthly limit columns. Index the actual
-- runtime lookup and constrain invalid overage actions.
CREATE INDEX IF NOT EXISTS idx_llm_quota_config_active_tenant
  ON public.llm_quota_config(tenant_id)
  WHERE is_active = true;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'llm_quota_config_overage_action_check'
  ) THEN
    ALTER TABLE public.llm_quota_config
      ADD CONSTRAINT llm_quota_config_overage_action_check
      CHECK (overage_action IN ('allow', 'warn', 'block'));
  END IF;
END $$;

-- Consolidate legacy proactive cron jobs into the durable user scheduler.
ALTER TABLE IF EXISTS public.user_scheduled_tasks
  ADD COLUMN IF NOT EXISTS cron_expression text;
ALTER TABLE IF EXISTS public.user_scheduled_tasks
  ADD COLUMN IF NOT EXISTS consecutive_failures integer NOT NULL DEFAULT 0;
ALTER TABLE IF EXISTS public.user_scheduled_tasks
  ADD COLUMN IF NOT EXISTS last_error text;
ALTER TABLE IF EXISTS public.user_scheduled_tasks
  ADD COLUMN IF NOT EXISTS locked_by text;
ALTER TABLE IF EXISTS public.user_scheduled_tasks
  ADD COLUMN IF NOT EXISTS locked_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_user_scheduled_tasks_due
  ON public.user_scheduled_tasks(next_execution_at)
  WHERE is_active = true AND locked_by IS NULL;

CREATE OR REPLACE FUNCTION public.claim_due_user_scheduled_tasks(
  p_worker_id text,
  p_due_before timestamptz,
  p_limit integer DEFAULT 5
)
RETURNS SETOF public.user_scheduled_tasks
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  WITH candidates AS (
    SELECT task.id
    FROM public.user_scheduled_tasks AS task
    WHERE task.is_active = true
      AND task.next_execution_at <= p_due_before
      AND COALESCE(task.consecutive_failures, 0) < 3
      AND (
        task.locked_by IS NULL
        OR task.locked_at < now() - interval '15 minutes'
      )
    ORDER BY task.next_execution_at
    FOR UPDATE SKIP LOCKED
    LIMIT LEAST(GREATEST(p_limit, 1), 20)
  ), claimed AS (
    UPDATE public.user_scheduled_tasks AS task
    SET locked_by = p_worker_id,
        locked_at = now()
    FROM candidates
    WHERE task.id = candidates.id
    RETURNING task.*
  )
  SELECT * FROM claimed;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_due_user_scheduled_tasks(text, timestamptz, integer)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_due_user_scheduled_tasks(text, timestamptz, integer)
  TO service_role;
