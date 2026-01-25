-- Seed Data for Project Nexus Mocking
-- 1. Users
insert into public.users (id, name, role, department)
values (
        'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        'Founder Boss',
        'founder',
        'Management'
    ),
    (
        'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12',
        'Sales Alice',
        'sales',
        'Sales Dept'
    ),
    (
        'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13',
        'Sales Bob',
        'sales',
        'Sales Dept'
    );
-- 2. Sales Leads (20 items)
insert into public.sales_leads (
        source_paper,
        professor,
        match_score,
        status,
        owner_id
    )
select 'Paper about AI ' || generate_series,
    'Prof. Number ' || generate_series,
    random() * 100,
    case
        when random() > 0.5 then 'new'::lead_status
        else 'contacted'::lead_status
    end,
    'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12'
from generate_series(1, 20);
-- 3. Approvals (5 items)
insert into public.approvals (
        type,
        requester_id,
        amount,
        details,
        ai_decision,
        status
    )
values (
        'travel',
        'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12',
        1200,
        'Trip to Shanghai',
        'auto',
        'approved'
    ),
    (
        'purchase',
        'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12',
        18000,
        'High-end GPU Server',
        'manual',
        'pending'
    ),
    (
        'expense',
        'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13',
        300,
        'Team Dinner',
        'auto',
        'approved'
    ),
    (
        'event',
        'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12',
        50000,
        'Annual Summit',
        'manual',
        'pending'
    ),
    (
        'travel',
        'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13',
        2500,
        'Trip to Beijing',
        'manual',
        'approved'
    );
-- 4. Incentives/Performance (Mock History)
insert into public.incentives (user_id, type, amount, reason, status)
values (
        'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12',
        'bonus',
        500,
        'Closed Big Deal',
        'paid'
    ),
    (
        'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13',
        'badge',
        0,
        'Badge: Cold Caller',
        'paid'
    );