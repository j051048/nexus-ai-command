-- Drop the overly permissive policy
DROP POLICY IF EXISTS "System can insert notifications" ON public.notifications;

-- Create proper insert policy - only boss can insert notifications OR system via service role
CREATE POLICY "Boss can insert notifications"
ON public.notifications
FOR INSERT
WITH CHECK (has_role(auth.uid(), 'boss'::app_role));