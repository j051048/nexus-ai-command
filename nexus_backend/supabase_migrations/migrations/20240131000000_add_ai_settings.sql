-- Create AI Settings Table
CREATE TABLE IF NOT EXISTS public.ai_settings (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id uuid REFERENCES public.users(id) NOT NULL,
    base_url text NOT NULL,
    api_key text,
    model text NOT NULL,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
-- Enable RLS
ALTER TABLE public.ai_settings ENABLE ROW LEVEL SECURITY;
-- Policy: Users can only see and update their own settings
CREATE POLICY "Users manage own AI settings" ON public.ai_settings FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
-- Create index for performance
CREATE INDEX idx_ai_settings_user ON public.ai_settings(user_id);
-- Grant permissions
GRANT ALL ON public.ai_settings TO authenticated;
GRANT ALL ON public.ai_settings TO service_role;