-- P1 observability hardening: durable agent node metrics and cost report RPC.

create table if not exists public.agent_node_metrics (
  id uuid primary key default gen_random_uuid(),
  node_name text not null,
  duration_ms integer not null default 0,
  success boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists idx_agent_node_metrics_created_at
  on public.agent_node_metrics (created_at desc);

create index if not exists idx_agent_node_metrics_node_created
  on public.agent_node_metrics (node_name, created_at desc);

alter table public.agent_node_metrics enable row level security;

drop policy if exists "service role can manage agent node metrics" on public.agent_node_metrics;
create policy "service role can manage agent node metrics"
  on public.agent_node_metrics
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create or replace function public.get_llm_cost_report(
  p_org_id uuid,
  p_start timestamptz,
  p_end timestamptz
)
returns table (
  model_code text,
  total_calls bigint,
  total_tokens bigint,
  total_cost_usd numeric,
  avg_duration_ms numeric
)
language sql
security definer
set search_path = public
as $$
  select
    coalesce(model_code, 'unknown') as model_code,
    count(*)::bigint as total_calls,
    coalesce(sum(total_tokens), 0)::bigint as total_tokens,
    coalesce(sum(call_cost), 0)::numeric as total_cost_usd,
    coalesce(avg(exec_time_ms), 0)::numeric as avg_duration_ms
  from public.llm_call_log
  where tenant_id = p_org_id
    and create_time >= p_start
    and create_time < p_end
  group by coalesce(model_code, 'unknown')
  order by total_cost_usd desc;
$$;

revoke all on function public.get_llm_cost_report(uuid, timestamptz, timestamptz)
  from public, anon, authenticated;
grant execute on function public.get_llm_cost_report(uuid, timestamptz, timestamptz)
  to service_role;
