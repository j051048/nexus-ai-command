-- Create sales_targets table for goal setting
CREATE TABLE public.sales_targets (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  target_type TEXT NOT NULL CHECK (target_type IN ('monthly', 'quarterly')),
  target_period TEXT NOT NULL, -- e.g., '2026-01' for monthly, '2026-Q1' for quarterly
  revenue_target NUMERIC DEFAULT 0,
  leads_target INTEGER DEFAULT 0,
  conversions_target INTEGER DEFAULT 0,
  win_rate_target NUMERIC DEFAULT 0,
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create approval_requests table
CREATE TABLE public.approval_requests (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('travel', 'purchase', 'expense', 'leave', 'activity')),
  description TEXT NOT NULL,
  amount NUMERIC DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'auto_approved', 'requires_boss', 'approved', 'rejected')),
  submitted_by UUID REFERENCES auth.users(id) NOT NULL,
  submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  reviewed_by UUID REFERENCES auth.users(id),
  reviewed_at TIMESTAMP WITH TIME ZONE,
  ai_reason TEXT,
  rejection_reason TEXT,
  metadata JSONB DEFAULT '{}'::jsonb
);

-- Create notifications table
CREATE TABLE public.notifications (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  read BOOLEAN DEFAULT false,
  data JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.sales_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approval_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- Sales targets policies (only boss can manage)
CREATE POLICY "Boss can manage sales targets"
ON public.sales_targets
FOR ALL
USING (has_role(auth.uid(), 'boss'::app_role));

CREATE POLICY "Everyone can view sales targets"
ON public.sales_targets
FOR SELECT
USING (true);

-- Approval requests policies
CREATE POLICY "Users can view own approvals"
ON public.approval_requests
FOR SELECT
USING (auth.uid() = submitted_by);

CREATE POLICY "Boss can view all approvals"
ON public.approval_requests
FOR SELECT
USING (has_role(auth.uid(), 'boss'::app_role));

CREATE POLICY "Users can submit approvals"
ON public.approval_requests
FOR INSERT
WITH CHECK (auth.uid() = submitted_by);

CREATE POLICY "Boss can update approvals"
ON public.approval_requests
FOR UPDATE
USING (has_role(auth.uid(), 'boss'::app_role));

-- Notifications policies
CREATE POLICY "Users can view own notifications"
ON public.notifications
FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can update own notifications"
ON public.notifications
FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "System can insert notifications"
ON public.notifications
FOR INSERT
WITH CHECK (true);

-- Enable realtime for notifications and approvals
ALTER PUBLICATION supabase_realtime ADD TABLE public.notifications;
ALTER PUBLICATION supabase_realtime ADD TABLE public.approval_requests;

-- Create trigger for updated_at
CREATE TRIGGER update_sales_targets_updated_at
BEFORE UPDATE ON public.sales_targets
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- Function to delete user and optionally transfer data
CREATE OR REPLACE FUNCTION public.transfer_and_delete_user(
  _user_to_delete UUID,
  _transfer_to_user UUID DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Check if caller is boss
  IF NOT has_role(auth.uid(), 'boss'::app_role) THEN
    RAISE EXCEPTION 'Only boss can perform this action';
  END IF;

  -- Transfer sales_metrics if target user specified
  IF _transfer_to_user IS NOT NULL THEN
    UPDATE public.sales_metrics 
    SET user_id = _transfer_to_user 
    WHERE user_id = _user_to_delete;
    
    UPDATE public.badges 
    SET user_id = _transfer_to_user 
    WHERE user_id = _user_to_delete;
  END IF;

  -- Delete user data (cascades will handle related records)
  DELETE FROM public.profiles WHERE user_id = _user_to_delete;
  DELETE FROM public.user_roles WHERE user_id = _user_to_delete;
  
  -- Note: Actual auth.users deletion needs to be done via admin API
END;
$$;