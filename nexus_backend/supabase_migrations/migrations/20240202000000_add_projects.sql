-- Create projects table for Project Management Module
-- Allows employees to manage projects and syncs with Boss view.
create table if not exists projects (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    description text,
    status text default 'planning',
    -- planning, in_progress, completed, on_hold
    progress int default 0,
    owner_id uuid references users(id) not null,
    start_date timestamptz default now(),
    end_date timestamptz,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
-- Realtime is essential for syncing between boss and employee
alter publication supabase_realtime
add table projects;
-- RLS
alter table projects enable row level security;
-- Policy: Users can see projects they own OR if they are boss (role='founder')
create policy "Users can view own projects or boss view all" on projects for
select using (
        auth.uid() = owner_id
        or exists (
            select 1
            from users
            where id = auth.uid()
                and role = 'founder'
        )
    );
create policy "Users can insert own projects" on projects for
insert with check (auth.uid() = owner_id);
create policy "Users can update own projects" on projects for
update using (auth.uid() = owner_id);
create policy "Boss can update all projects" on projects for
update using (
        exists (
            select 1
            from users
            where id = auth.uid()
                and role = 'founder'
        )
    );
-- Project Timeline (Events)
create table if not exists project_timeline (
    id uuid primary key default gen_random_uuid(),
    project_id uuid references projects(id) on delete cascade not null,
    title text not null,
    content text,
    event_type text,
    -- milestone, meeting, dinner
    created_by uuid references users(id),
    created_at timestamptz default now()
);
alter table project_timeline enable row level security;
create policy "Users can see timeline of visible projects" on project_timeline for
select using (
        exists (
            select 1
            from projects
            where projects.id = project_timeline.project_id
                and (
                    projects.owner_id = auth.uid()
                    or exists(
                        select 1
                        from users
                        where id = auth.uid()
                            and role = 'founder'
                    )
                )
        )
    );
create policy "Users can insert timeline to visible projects" on project_timeline for
insert with check (
        exists (
            select 1
            from projects
            where projects.id = project_timeline.project_id
                and (
                    projects.owner_id = auth.uid()
                    or exists(
                        select 1
                        from users
                        where id = auth.uid()
                            and role = 'founder'
                    )
                )
        )
    );