-- P1 durability baseline for long-running Agent execution.

CREATE TABLE IF NOT EXISTS public.agent_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id text UNIQUE,
  thread_id text,
  trace_id text,
  organization_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  session_id text,
  scene_code text,
  agent_code text,
  status text NOT NULL DEFAULT 'running',
  input_summary text,
  output_summary text,
  final_response text,
  error text,
  error_message text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  input_tokens integer NOT NULL DEFAULT 0,
  output_tokens integer NOT NULL DEFAULT 0,
  cost_usd numeric(12, 6) NOT NULL DEFAULT 0,
  duration_ms integer,
  total_input_tokens integer NOT NULL DEFAULT 0,
  total_output_tokens integer NOT NULL DEFAULT 0,
  total_cost numeric(12, 6) NOT NULL DEFAULT 0,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_tool_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_run_id uuid REFERENCES public.agent_runs(id) ON DELETE CASCADE,
  run_id text REFERENCES public.agent_runs(run_id) ON DELETE CASCADE,
  organization_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  tool_call_id text,
  tool_name text NOT NULL,
  status text NOT NULL DEFAULT 'pending',
  risk text NOT NULL DEFAULT 'low',
  tool_args jsonb NOT NULL DEFAULT '{}'::jsonb,
  args jsonb NOT NULL DEFAULT '{}'::jsonb,
  result_preview text,
  error_type text,
  error_message text,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  duration_ms integer
);

CREATE TABLE IF NOT EXISTS public.agent_events (
  id bigserial PRIMARY KEY,
  agent_run_id uuid REFERENCES public.agent_runs(id) ON DELETE CASCADE,
  run_id text REFERENCES public.agent_runs(run_id) ON DELETE CASCADE,
  organization_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  event_type text NOT NULL,
  node_name text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.agent_runs
  ADD COLUMN IF NOT EXISTS run_id text,
  ADD COLUMN IF NOT EXISTS thread_id text,
  ADD COLUMN IF NOT EXISTS trace_id text,
  ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS session_id text,
  ADD COLUMN IF NOT EXISTS scene_code text,
  ADD COLUMN IF NOT EXISTS agent_code text,
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'running',
  ADD COLUMN IF NOT EXISTS final_response text,
  ADD COLUMN IF NOT EXISTS error text,
  ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS input_tokens integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS output_tokens integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cost_usd numeric(12, 6) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS duration_ms integer,
  ADD COLUMN IF NOT EXISTS finished_at timestamptz,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_runs_run_id_unique
  ON public.agent_runs(run_id);

ALTER TABLE public.agent_tool_calls
  ADD COLUMN IF NOT EXISTS agent_run_id uuid REFERENCES public.agent_runs(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS run_id text REFERENCES public.agent_runs(run_id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS tool_call_id text,
  ADD COLUMN IF NOT EXISTS tool_name text,
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS risk text NOT NULL DEFAULT 'low',
  ADD COLUMN IF NOT EXISTS tool_args jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS args jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS result_preview text,
  ADD COLUMN IF NOT EXISTS error_type text,
  ADD COLUMN IF NOT EXISTS error_message text,
  ADD COLUMN IF NOT EXISTS duration_ms integer;

ALTER TABLE public.agent_events
  ADD COLUMN IF NOT EXISTS agent_run_id uuid REFERENCES public.agent_runs(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS run_id text REFERENCES public.agent_runs(run_id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS event_type text,
  ADD COLUMN IF NOT EXISTS node_name text,
  ADD COLUMN IF NOT EXISTS payload jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_agent_runs_org_status
  ON public.agent_runs(organization_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_run
  ON public.agent_tool_calls(agent_run_id, started_at);
CREATE INDEX IF NOT EXISTS idx_agent_events_run
  ON public.agent_events(agent_run_id, id);

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
