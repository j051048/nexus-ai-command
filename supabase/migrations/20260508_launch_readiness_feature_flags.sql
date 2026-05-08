-- Launch readiness: tenant-scoped feature flags and minimal safe defaults.
-- This migration is additive and safe for existing Supabase projects.

create table if not exists public.feature_flags (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid null,
  flag_key text not null,
  enabled boolean not null default false,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_feature_flags_org_key
  on public.feature_flags (organization_id, flag_key);

create unique index if not exists idx_feature_flags_global_key_unique
  on public.feature_flags (flag_key)
  where organization_id is null;

create unique index if not exists idx_feature_flags_tenant_key_unique
  on public.feature_flags (organization_id, flag_key)
  where organization_id is not null;

alter table public.feature_flags enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'feature_flags'
      and policyname = 'feature_flags_service_role_all'
  ) then
    create policy feature_flags_service_role_all
      on public.feature_flags
      for all
      using (auth.role() = 'service_role')
      with check (auth.role() = 'service_role');
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'feature_flags'
      and policyname = 'feature_flags_authenticated_read'
  ) then
    create policy feature_flags_authenticated_read
      on public.feature_flags
      for select
      using (
        organization_id is null
        or organization_id::text = coalesce(auth.jwt() ->> 'organization_id', '')
        or organization_id::text = coalesce(auth.jwt() -> 'app_metadata' ->> 'organization_id', '')
      );
  end if;
end $$;

with defaults(flag_key, enabled, description) as (
  values
    ('module.crm', true, 'Core customer and sales management'),
    ('module.documents', true, 'Document and contract workspace'),
    ('module.knowledge', true, 'Knowledge base and graph'),
    ('module.approval', true, 'Approval and OA workflows'),
    ('module.finance', true, 'Finance center'),
    ('module.work_orders', true, 'Work order management'),
    ('module.sales', true, 'Sales workflows'),
    ('module.projects', true, 'Project tracking'),
    ('module.reports', true, 'Standard reports'),
    ('module.billing', true, 'Subscription and billing'),
    ('module.vmd', false, 'Beta VMD marketing command center'),
    ('module.plugins', false, 'Beta plugin marketplace'),
    ('module.tender', false, 'Beta tender analysis'),
    ('module.battlecards', false, 'Beta battlecard library'),
    ('module.training', false, 'Beta training center'),
    ('module.inventory', false, 'Beta inventory management'),
    ('module.assets', false, 'Beta asset management'),
    ('module.certificates', false, 'Beta certificate management'),
    ('module.hr', false, 'Beta HR center'),
    ('module.workflow_designer', false, 'Beta workflow designer'),
    ('module.form_designer', false, 'Beta form designer'),
    ('module.report_builder', false, 'Beta custom report builder'),
    ('module.custom_dashboard', false, 'Beta custom dashboard'),
    ('module.soul_document', false, 'Beta soul document'),
    ('module.dev_tools', false, 'Internal developer tools')
),
updated as (
  update public.feature_flags f
  set
    enabled = d.enabled,
    description = d.description,
    updated_at = now()
  from defaults d
  where f.organization_id is null
    and f.flag_key = d.flag_key
  returning f.flag_key
)
insert into public.feature_flags (organization_id, flag_key, enabled, description)
select null, d.flag_key, d.enabled, d.description
from defaults d
where not exists (
  select 1 from updated u where u.flag_key = d.flag_key
)
and not exists (
  select 1
  from public.feature_flags f
  where f.organization_id is null
    and f.flag_key = d.flag_key
);
