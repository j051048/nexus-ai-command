-- ============================================
-- Fix Missing Tables Baseline
-- Version: 20260501_001
-- Description: Creates missing tables profiles, ai_settings, sales_metrics, projects and fixes approval_requests.
-- ============================================

-- 1. profiles
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    role TEXT DEFAULT 'employee',
    department TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. ai_settings
CREATE TABLE IF NOT EXISTS public.ai_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL,
    base_url TEXT NOT NULL,
    api_key TEXT,
    model TEXT NOT NULL,
    behavior_preferences JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, organization_id)
);

-- 3. sales_metrics
CREATE TABLE IF NOT EXISTS public.sales_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    pipeline_value NUMERIC DEFAULT 0,
    win_rate NUMERIC DEFAULT 0,
    calls_made INTEGER DEFAULT 0,
    deals_closed INTEGER DEFAULT 0,
    period TEXT DEFAULT 'weekly',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. projects
CREATE TABLE IF NOT EXISTS public.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    name TEXT NOT NULL,
    description TEXT,
    stage TEXT DEFAULT 'planning',
    type TEXT DEFAULT 'Enterprise',
    progress NUMERIC DEFAULT 0,
    member_ids UUID[],
    start_date DATE,
    end_date DATE,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Fix approval_requests
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS type TEXT;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS amount NUMERIC;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS submitted_by UUID REFERENCES auth.users(id);
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS ai_reason TEXT;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS on_behalf_of UUID;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS submitted_via TEXT;

-- Update RLS for new tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sales_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable read access for all users" ON public.profiles FOR SELECT USING (true);
CREATE POLICY "Enable all access for own profile" ON public.profiles USING (auth.uid() = id);

CREATE POLICY "Enable read for own ai_settings" ON public.ai_settings FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Enable insert for own ai_settings" ON public.ai_settings FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Enable update for own ai_settings" ON public.ai_settings FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Enable read for own sales_metrics" ON public.sales_metrics FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Enable all for own sales_metrics" ON public.sales_metrics USING (auth.uid() = user_id);

CREATE POLICY "Enable read for own projects" ON public.projects FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Enable all for own projects" ON public.projects USING (auth.uid() = user_id);
