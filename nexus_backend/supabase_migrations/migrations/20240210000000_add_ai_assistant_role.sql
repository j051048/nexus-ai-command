-- Migration: Add AI Assistant Role for 3-tier Permission System
-- Level 1: founder (boss) - Full admin access
-- Level 2: ai_assistant - Can act on behalf of employees, limited data access
-- Level 3: sales/employee - Basic user access

-- 1. Add ai_assistant to the user_role enum
ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'ai_assistant';

-- 2. Add columns to track delegation (when AI acts on behalf of employee)
ALTER TABLE public.approval_requests 
ADD COLUMN IF NOT EXISTS on_behalf_of uuid REFERENCES public.users(id),
ADD COLUMN IF NOT EXISTS submitted_via text DEFAULT 'direct'; -- 'direct' | 'ai_assistant' | 'api'

-- 3. Create AI Assistant user (豆豆) - will be inserted once
-- This is a system user, not tied to auth.users
INSERT INTO public.users (id, name, role, department, created_at)
VALUES (
    '00000000-0000-0000-0000-000000000001', -- Fixed UUID for AI Assistant
    '豆豆',
    'ai_assistant',
    'AI Center',
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- 4. Create function to submit approval on behalf of employee
CREATE OR REPLACE FUNCTION submit_approval_on_behalf(
    _employee_id uuid,
    _type approval_type,
    _amount numeric,
    _details text,
    _ai_decision ai_decision_type DEFAULT 'manual',
    _ai_reasoning text DEFAULT NULL
)
RETURNS uuid AS $$
DECLARE
    _new_id uuid;
    _ai_user_id uuid := '00000000-0000-0000-0000-000000000001';
BEGIN
    -- Verify employee exists and is not a boss
    IF NOT EXISTS (SELECT 1 FROM public.users WHERE id = _employee_id AND role IN ('sales', 'employee')) THEN
        RAISE EXCEPTION 'Invalid employee ID or insufficient permissions';
    END IF;

    INSERT INTO public.approval_requests (
        requester_id,
        on_behalf_of,
        submitted_via,
        type,
        amount,
        details,
        ai_decision,
        ai_reasoning,
        status,
        created_at
    ) VALUES (
        _employee_id,  -- The actual requester is the employee
        _employee_id,  -- on_behalf_of also points to employee (for clarity)
        'ai_assistant',
        _type,
        _amount,
        _details,
        _ai_decision,
        _ai_reasoning,
        'pending',
        NOW()
    ) RETURNING id INTO _new_id;

    -- Log the action
    INSERT INTO public.audit_logs (action, actor_user_id, target_id, target_table, details_json)
    VALUES (
        'approval_submitted_via_ai',
        _ai_user_id,
        _new_id,
        'approval_requests',
        jsonb_build_object(
            'employee_id', _employee_id,
            'type', _type,
            'amount', _amount
        )
    );

    RETURN _new_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 5. Update get_user_role to handle ai_assistant
CREATE OR REPLACE FUNCTION public.get_user_role(_user_id uuid)
RETURNS text AS $$
DECLARE
    _role public.user_role;
BEGIN
    SELECT role INTO _role FROM public.users WHERE id = _user_id;
    
    IF _role = 'founder' THEN 
        RETURN 'boss';
    ELSIF _role = 'ai_assistant' THEN 
        RETURN 'ai_assistant';
    ELSIF _role = 'sales' THEN 
        RETURN 'employee';
    ELSE 
        RETURN 'employee';
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 6. Create RLS policies for AI Assistant data access
-- AI Assistant can read employee data (for helping them)
CREATE POLICY "AI Assistant can read employee data" ON public.users
FOR SELECT USING (
    EXISTS (
        SELECT 1 FROM public.users 
        WHERE id = auth.uid() AND role IN ('founder', 'ai_assistant')
    )
);

-- AI Assistant can insert approval_requests on behalf of employees
CREATE POLICY "AI Assistant can submit approvals" ON public.approval_requests
FOR INSERT WITH CHECK (
    -- Direct submission by the user themselves
    requester_id = auth.uid()
    OR
    -- Submission via AI assistant (system call)
    submitted_via = 'ai_assistant'
);

-- 7. Grant permissions for the new function
GRANT EXECUTE ON FUNCTION submit_approval_on_behalf TO authenticated;
GRANT EXECUTE ON FUNCTION submit_approval_on_behalf TO service_role;

-- 8. Create view for boss to see all approvals with proper attribution
CREATE OR REPLACE VIEW approval_requests_with_details AS
SELECT 
    ar.*,
    u.name as requester_name,
    u.department as requester_department,
    CASE 
        WHEN ar.submitted_via = 'ai_assistant' THEN '豆豆代提交'
        ELSE '直接提交'
    END as submission_method
FROM public.approval_requests ar
LEFT JOIN public.users u ON ar.requester_id = u.id;

COMMENT ON VIEW approval_requests_with_details IS 'Approval requests with requester details and submission method';