-- Create Notifications Table
CREATE TABLE public.notifications (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id uuid REFERENCES public.users(id) NOT NULL,
    type text NOT NULL CHECK (type IN ('info', 'success', 'warning', 'error')),
    title text NOT NULL,
    message text,
    read boolean DEFAULT false,
    link text,
    -- Action link if needed
    created_at timestamptz DEFAULT now()
);
-- Enable RLS
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
-- Policy: Users can only see their own notifications
CREATE POLICY "Users receive own notifications" ON public.notifications FOR
SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can update own notifications" ON public.notifications FOR
UPDATE USING (auth.uid() = user_id);
-- Indexes
CREATE INDEX idx_notifications_user_read ON public.notifications(user_id, read);
CREATE INDEX idx_notifications_created ON public.notifications(created_at DESC);
-- Grant permissions
GRANT ALL ON public.notifications TO authenticated;
GRANT ALL ON public.notifications TO service_role;