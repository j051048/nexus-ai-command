-- P1 enterprise SSO, compliance evidence, and RLS-as-code baseline.

create table if not exists public.compliance_evidence_events (
  id uuid primary key default gen_random_uuid(),
  control_id text not null,
  framework text not null,
  evidence_type text not null,
  description text not null,
  actor_user_id uuid,
  org_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_compliance_evidence_framework_created
  on public.compliance_evidence_events (framework, created_at desc);

create index if not exists idx_compliance_evidence_org_created
  on public.compliance_evidence_events (org_id, created_at desc);

alter table public.compliance_evidence_events enable row level security;

drop policy if exists "tenant can read own compliance evidence" on public.compliance_evidence_events;
create policy "tenant can read own compliance evidence"
  on public.compliance_evidence_events
  for select
  using (org_id::text = auth.jwt() ->> 'org_id' or auth.role() = 'service_role');

drop policy if exists "service role can write compliance evidence" on public.compliance_evidence_events;
create policy "service role can write compliance evidence"
  on public.compliance_evidence_events
  for insert
  with check (auth.role() = 'service_role');

create table if not exists public.enterprise_sso_login_events (
  id uuid primary key default gen_random_uuid(),
  org_id uuid,
  provider_code text not null,
  subject text,
  email text,
  status text not null check (status in ('success', 'failed')),
  error_message text,
  created_at timestamptz not null default now()
);

create index if not exists idx_enterprise_sso_login_events_org_created
  on public.enterprise_sso_login_events (org_id, created_at desc);

alter table public.enterprise_sso_login_events enable row level security;

drop policy if exists "service role can manage sso login events" on public.enterprise_sso_login_events;
create policy "service role can manage sso login events"
  on public.enterprise_sso_login_events
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create or replace function public.nexus_enable_org_rls(p_table regclass, p_org_column text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = replace(p_table::text, 'public.', '')
      and column_name = p_org_column
  ) then
    return;
  end if;

  execute format('alter table %s enable row level security', p_table);
  execute format('drop policy if exists "tenant can select own rows" on %s', p_table);
  execute format(
    'create policy "tenant can select own rows" on %s for select using (%I::text = auth.jwt() ->> ''org_id'' or auth.role() = ''service_role'')',
    p_table,
    p_org_column
  );
  execute format('drop policy if exists "tenant can insert own rows" on %s', p_table);
  execute format(
    'create policy "tenant can insert own rows" on %s for insert with check (%I::text = auth.jwt() ->> ''org_id'' or auth.role() = ''service_role'')',
    p_table,
    p_org_column
  );
  execute format('drop policy if exists "tenant can update own rows" on %s', p_table);
  execute format(
    'create policy "tenant can update own rows" on %s for update using (%I::text = auth.jwt() ->> ''org_id'' or auth.role() = ''service_role'') with check (%I::text = auth.jwt() ->> ''org_id'' or auth.role() = ''service_role'')',
    p_table,
    p_org_column,
    p_org_column
  );
end;
$$;

do $$
begin
  if to_regclass('public.crm_customers') is not null then
    perform public.nexus_enable_org_rls('public.crm_customers'::regclass, 'organization_id');
  end if;
  if to_regclass('public.sales_leads') is not null then
    perform public.nexus_enable_org_rls('public.sales_leads'::regclass, 'organization_id');
  end if;
  if to_regclass('public.approval_requests') is not null then
    perform public.nexus_enable_org_rls('public.approval_requests'::regclass, 'organization_id');
  end if;
  if to_regclass('public.workflows') is not null then
    perform public.nexus_enable_org_rls('public.workflows'::regclass, 'organization_id');
  end if;
  if to_regclass('public.llm_call_log') is not null then
    perform public.nexus_enable_org_rls('public.llm_call_log'::regclass, 'org_id');
  end if;
  if to_regclass('public.tool_execution_audit') is not null then
    perform public.nexus_enable_org_rls('public.tool_execution_audit'::regclass, 'org_id');
  end if;
  if to_regclass('public.audit_logs') is not null then
    perform public.nexus_enable_org_rls('public.audit_logs'::regclass, 'org_id');
  end if;
end $$;
