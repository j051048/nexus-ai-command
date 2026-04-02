-- Migration: Add consistent organization_id to OA and VMD tables
-- Date: 2026-04-02
-- Purpose: Fix 500 errors and enable auto-filtering for OA and VMD modules.

-- ====== 1. OA Tables ======

-- oa_leave_requests
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'oa_leave_requests' AND column_name = 'organization_id') THEN
        ALTER TABLE public.oa_leave_requests ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_oa_leave_requests_org ON public.oa_leave_requests(organization_id);

-- oa_tasks
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'oa_tasks' AND column_name = 'organization_id') THEN
        ALTER TABLE public.oa_tasks ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_oa_tasks_org ON public.oa_tasks(organization_id);

-- oa_work_handovers
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'oa_work_handovers' AND column_name = 'organization_id') THEN
        ALTER TABLE public.oa_work_handovers ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_oa_work_handovers_org ON public.oa_work_handovers(organization_id);

-- oa_meeting_rooms
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'oa_meeting_rooms' AND column_name = 'organization_id') THEN
        ALTER TABLE public.oa_meeting_rooms ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_oa_meeting_rooms_org ON public.oa_meeting_rooms(organization_id);


-- ====== 2. VMD Tables (Adding organization_id for consistency with OrgFilteredClient) ======

-- business_clue
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'business_clue' AND column_name = 'organization_id') THEN
        ALTER TABLE public.business_clue ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
        -- Sync from tenant_id if exists
        UPDATE public.business_clue SET organization_id = tenant_id WHERE organization_id IS NULL AND tenant_id IS NOT NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_business_clue_org ON public.business_clue(organization_id);

-- vmd_main_task
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_main_task' AND column_name = 'organization_id') THEN
        ALTER TABLE public.vmd_main_task ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
        -- Sync from tenant_id
        UPDATE public.vmd_main_task SET organization_id = tenant_id WHERE organization_id IS NULL AND tenant_id IS NOT NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_vmd_main_task_org ON public.vmd_main_task(organization_id);

-- vmd_sub_task
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_sub_task' AND column_name = 'organization_id') THEN
        ALTER TABLE public.vmd_sub_task ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
        -- Sync from tenant_id
        UPDATE public.vmd_sub_task SET organization_id = tenant_id WHERE organization_id IS NULL AND tenant_id IS NOT NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_vmd_sub_task_org ON public.vmd_sub_task(organization_id);

-- vmd_agent_config
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_agent_config' AND column_name = 'organization_id') THEN
        ALTER TABLE public.vmd_agent_config ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
        -- Sync from tenant_id
        UPDATE public.vmd_agent_config SET organization_id = tenant_id WHERE organization_id IS NULL AND tenant_id IS NOT NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_vmd_agent_config_org ON public.vmd_agent_config(organization_id);


-- ====== 3. RLS Polices Update for OA Tables (missing in initial migration) ======

ALTER TABLE public.oa_leave_requests ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for OA Leave Requests" ON public.oa_leave_requests;
CREATE POLICY "Org Isolation for OA Leave Requests" ON public.oa_leave_requests 
FOR ALL TO authenticated USING (organization_id = (SELECT (auth.jwt() -> 'user_metadata' ->> 'org_id')::UUID));

ALTER TABLE public.oa_tasks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for OA Tasks" ON public.oa_tasks;
CREATE POLICY "Org Isolation for OA Tasks" ON public.oa_tasks 
FOR ALL TO authenticated USING (organization_id = (SELECT (auth.jwt() -> 'user_metadata' ->> 'org_id')::UUID));
