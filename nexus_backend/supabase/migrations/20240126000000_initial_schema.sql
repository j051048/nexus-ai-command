-- Enable necessary extensions
create extension if not exists "uuid-ossp";
-- 1. Enums for type safety
create type user_role as enum ('founder', 'sales', 'employee');
create type lead_status as enum ('new', 'contacted', 'qualified', 'lost', 'won');
create type incentive_type as enum ('bonus', 'badge', 'rank');
create type approval_type as enum ('purchase', 'travel', 'event', 'expense');
create type approval_status as enum ('pending', 'approved', 'rejected');
create type ai_decision_type as enum ('auto', 'manual');
-- 2. Users Table
create table public.users (
    id uuid primary key default uuid_generate_v4(),
    name text not null,
    role user_role not null default 'sales',
    department text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
-- 3. Sales Leads Table
create table public.sales_leads (
    id uuid primary key default uuid_generate_v4(),
    source_paper text,
    professor text,
    match_score float,
    status lead_status default 'new',
    owner_id uuid references public.users(id),
    ai_win_probability float default 0.0,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
-- 4. Opportunities Table
create table public.opportunities (
    id uuid primary key default uuid_generate_v4(),
    lead_id uuid references public.sales_leads(id),
    stage text not null,
    value numeric(12, 2) default 0,
    ai_performance_score float,
    last_activity timestamptz default now(),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
-- 5. Performance Scores (Daily/Weekly)
create table public.performance_scores (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid references public.users(id) not null,
    date date default current_date,
    daily_score float default 0,
    dimensions_json jsonb default '{"follow_up":0, "call_quality":0, "win_rate":0}',
    total_bonus numeric(10, 2) default 0,
    created_at timestamptz default now()
);
-- 6. Incentives (Event Driven)
create table public.incentives (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid references public.users(id) not null,
    type incentive_type not null,
    amount numeric(10, 2) default 0,
    badge_name text,
    -- Only if type is badge
    reason text,
    triggered_at timestamptz default now(),
    status text default 'pending' -- pending, paid, mock_synced
);
-- 7. Badges (Gamification)
create table public.badges (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid references public.users(id) not null,
    badge_name text not null,
    unlocked_at timestamptz default now()
);
-- 8. Approvals (AI & Boss)
create table public.approvals (
    id uuid primary key default uuid_generate_v4(),
    type approval_type not null,
    requester_id uuid references public.users(id) not null,
    amount numeric(12, 2) default 0,
    details text,
    ai_decision ai_decision_type default 'manual',
    ai_reasoning text,
    status approval_status default 'pending',
    boss_approved boolean default false,
    processed_at timestamptz,
    created_at timestamptz default now()
);
-- 9. Audit Logs (Immutable)
create table public.audit_logs (
    id uuid primary key default uuid_generate_v4(),
    action text not null,
    actor_user_id uuid references public.users(id),
    target_id uuid,
    target_table text,
    details_json jsonb,
    timestamp timestamptz default now()
);
-- 10. Indexes for Performance
create index idx_leads_owner on public.sales_leads(owner_id);
create index idx_leads_status on public.sales_leads(status);
create index idx_perf_user_date on public.performance_scores(user_id, date);
create index idx_incentives_status on public.incentives(status);
-- 11. Row Level Security (RLS) - Basic Setup using Supabase auth
alter table public.users enable row level security;
alter table public.sales_leads enable row level security;
alter table public.opportunities enable row level security;
alter table public.performance_scores enable row level security;
alter table public.incentives enable row level security;
alter table public.approvals enable row level security;
alter table public.audit_logs enable row level security;
-- Policy: Users can see their own data, Founders see all
create policy "Users see own data" on public.sales_leads for
select using (auth.uid() = owner_id);
create policy "Founders ensure control" on public.sales_leads for all using (
    exists (
        select 1
        from public.users
        where id = auth.uid()
            and role = 'founder'
    )
);
-- Trigger: Automatically update updated_at
create or replace function update_modified_column() returns trigger as $$ begin new.updated_at = now();
return new;
end;
$$ language 'plpgsql';
create trigger update_leads_modtime before
update on public.sales_leads for each row execute procedure update_modified_column();
-- Function: Protect Audit Logs (Append Only)
create or replace function prevent_audit_update() returns trigger as $$ begin raise exception 'Audit logs are immutable!';
end;
$$ language 'plpgsql';
create trigger no_update_audit before
update
    or delete on public.audit_logs for each row execute procedure prevent_audit_update();