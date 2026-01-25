-- 1. Create Business Tables (if they don't exist)
CREATE TABLE IF NOT EXISTS public.sales_metrics (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id uuid REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
    metric_type text NOT NULL,
    value numeric DEFAULT 0,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.badges (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id uuid REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
    name text NOT NULL,
    icon text,
    awarded_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.approval_requests (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    submitted_by uuid REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
    type approval_type NOT NULL,
    amount numeric NOT NULL,
    description text,
    status approval_status DEFAULT 'pending',
    ai_decision ai_decision_type DEFAULT 'manual',
    ai_reason text,
    created_at timestamptz DEFAULT now()
);
-- 2. Enable RLS
ALTER TABLE public.sales_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.badges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approval_requests ENABLE ROW LEVEL SECURITY;
-- 3. RLS Policies (Simplified for Boss Management)
CREATE POLICY "Enable all for users" ON public.sales_metrics FOR ALL USING (true);
CREATE POLICY "Enable all for users" ON public.badges FOR ALL USING (true);
CREATE POLICY "Enable all for users" ON public.approval_requests FOR ALL USING (true);
-- 4. RPC: Transfer Employee Data
-- This function atomically moves all business assets from one user to another
CREATE OR REPLACE FUNCTION public.transfer_employee_data(from_user_id uuid, to_user_id uuid) RETURNS void AS $$ BEGIN -- Transfer Metrics
UPDATE public.sales_metrics
SET user_id = to_user_id
WHERE user_id = from_user_id;
-- Transfer Badges
UPDATE public.badges
SET user_id = to_user_id
WHERE user_id = from_user_id;
-- Transfer Approvals
UPDATE public.approval_requests
SET submitted_by = to_user_id
WHERE submitted_by = from_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
-- 5. RPC: Delete Employee (Business Layer Only)
-- This removes the user from the public business registry.
-- Note: It does NOT remove the login account (auth.users) as that requires Admin API.
CREATE OR REPLACE FUNCTION public.delete_employee(target_user_id uuid) RETURNS void AS $$ BEGIN
DELETE FROM public.users
WHERE id = target_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;