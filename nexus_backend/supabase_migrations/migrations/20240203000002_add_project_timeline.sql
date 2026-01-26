-- Create project_timeline table for granular project event tracking
CREATE TABLE IF NOT EXISTS public.project_timeline (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid REFERENCES public.projects(id) ON DELETE CASCADE,
    title text NOT NULL,
    content text,
    event_type text CHECK (
        event_type IN (
            'milestone',
            'meeting',
            'dinner',
            'task',
            'other'
        )
    ),
    created_at timestamptz DEFAULT now(),
    created_by uuid REFERENCES public.users(id)
);
-- Enable RLS
ALTER TABLE public.project_timeline ENABLE ROW LEVEL SECURITY;
-- Simple RLS Policy: Users can only see events for projects they own OR events they created
CREATE POLICY "Users can view relevant project timeline events" ON public.project_timeline FOR
SELECT USING (
        created_by = auth.uid()
        OR project_id IN (
            SELECT id
            FROM public.projects
            WHERE owner_id = auth.uid()
        )
    );
CREATE POLICY "Users can insert their own events" ON public.project_timeline FOR
INSERT WITH CHECK (created_by = auth.uid());