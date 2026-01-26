-- Create AI settings table for boss configuration
CREATE TABLE public.ai_settings (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL UNIQUE,
  base_url TEXT DEFAULT 'https://ai.gateway.zhz-tech.dev/v1/chat/completions',
  api_key TEXT,
  model TEXT DEFAULT 'google/gemini-3-pro-preview',
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
-- Enable RLS
ALTER TABLE public.ai_settings ENABLE ROW LEVEL SECURITY;
-- Only boss can manage AI settings
CREATE POLICY "Boss can view ai_settings" ON public.ai_settings FOR
SELECT USING (
    EXISTS (
      SELECT 1
      FROM public.user_roles
      WHERE user_roles.user_id = auth.uid()
        AND user_roles.role = 'boss'
    )
  );
CREATE POLICY "Boss can insert ai_settings" ON public.ai_settings FOR
INSERT WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.user_roles
      WHERE user_roles.user_id = auth.uid()
        AND user_roles.role = 'boss'
    )
  );
CREATE POLICY "Boss can update ai_settings" ON public.ai_settings FOR
UPDATE USING (
    EXISTS (
      SELECT 1
      FROM public.user_roles
      WHERE user_roles.user_id = auth.uid()
        AND user_roles.role = 'boss'
    )
  );
-- Trigger for updated_at
CREATE TRIGGER update_ai_settings_updated_at BEFORE
UPDATE ON public.ai_settings FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();