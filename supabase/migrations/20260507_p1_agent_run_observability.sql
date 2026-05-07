-- P1 durability baseline for long-running Agent execution.

CREATE TABLE IF NOT EXISTS public.agent_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id text UNIQUE NOT NULL,
  organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  session_id text,
  scene_code text,
  agent_code text,
  status text NOT NULL DEFAULT 'running',
  input_summary text,
  output_summary text,
  error_message text,
  total_input_tokens integer NOT NULL DEFAULT 0,
  total_output_tokens integer NOT NULL DEFAULT 0,
  total_cost numeric(12, 6) NOT NULL DEFAULT 0,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_tool_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id text NOT NULL REFERENCES public.agent_runs(run_id) ON DELETE CASCADE,
  organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  tool_call_id text,
  tool_name text NOT NULL,
  status text NOT NULL DEFAULT 'pending',
  risk text NOT NULL DEFAULT 'low',
  args jsonb NOT NULL DEFAULT '{}'::jsonb,
  result_preview text,
  error_message text,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  duration_ms integer
);

CREATE TABLE IF NOT EXISTS public.agent_events (
  id bigserial PRIMARY KEY,
  run_id text NOT NULL REFERENCES public.agent_runs(run_id) ON DELETE CASCADE,
  organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  event_type text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_org_status
  ON public.agent_runs(organization_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_run
  ON public.agent_tool_calls(run_id, started_at);
CREATE INDEX IF NOT EXISTS idx_agent_events_run
  ON public.agent_events(run_id, id);

ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_tool_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agent_runs_org_select ON public.agent_runs;
CREATE POLICY agent_runs_org_select ON public.agent_runs
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS agent_tool_calls_org_select ON public.agent_tool_calls;
CREATE POLICY agent_tool_calls_org_select ON public.agent_tool_calls
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS agent_events_org_select ON public.agent_events;
CREATE POLICY agent_events_org_select ON public.agent_events
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS agent_runs_service_write ON public.agent_runs;
CREATE POLICY agent_runs_service_write ON public.agent_runs
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS agent_tool_calls_service_write ON public.agent_tool_calls;
CREATE POLICY agent_tool_calls_service_write ON public.agent_tool_calls
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS agent_events_service_write ON public.agent_events;
CREATE POLICY agent_events_service_write ON public.agent_events
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);
