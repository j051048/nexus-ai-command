import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';

export interface AISettings {
  id: string;
  user_id: string;
  base_url: string;
  api_key: string | null;
  model: string;
  created_at: string;
  updated_at: string;
}

export const DEFAULT_MODELS = [
  { value: 'google/gemini-3-pro-preview', label: 'Gemini 3 Pro Preview (推荐)' },
  { value: 'google/gemini-3-flash-preview', label: 'Gemini 3 Flash Preview' },
  { value: 'google/gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
  { value: 'google/gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
  { value: 'openai/gpt-5.2', label: 'GPT-5.2 (最新)' },
  { value: 'openai/gpt-5', label: 'GPT-5' },
  { value: 'openai/gpt-5-mini', label: 'GPT-5 Mini' },
  { value: 'anthropic/claude-4-opus', label: 'Claude 4 Opus' },
  { value: 'anthropic/claude-4-sonnet', label: 'Claude 4 Sonnet' },
  { value: 'mistral/mistral-large-2', label: 'Mistral Large 2' },
  { value: 'meta/llama-4-405b', label: 'Llama 4 405B' },
  { value: 'custom', label: '自定义模型...' },
];

export function useAISettings() {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['ai-settings'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('ai_settings')
        .select('*')
        .maybeSingle();

      if (error) throw error;
      return data as AISettings | null;
    },
    enabled: !!user,
  });
}

export function useSaveAISettings() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  return useMutation({
    mutationFn: async (settings: { base_url: string; api_key: string | null; model: string }) => {
      // Check if settings exist
      const { data: existing } = await supabase
        .from('ai_settings')
        .select('id')
        .maybeSingle();

      if (existing) {
        const { data, error } = await supabase
          .from('ai_settings')
          .update({
            base_url: settings.base_url,
            api_key: settings.api_key,
            model: settings.model,
          })
          .eq('id', existing.id)
          .select()
          .single();

        if (error) throw error;
        return data;
      } else {
        const { data, error } = await supabase
          .from('ai_settings')
          .insert({
            user_id: user?.id,
            base_url: settings.base_url,
            api_key: settings.api_key,
            model: settings.model,
          })
          .select()
          .single();

        if (error) throw error;
        return data;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] });
    },
  });
}

export function useTestAIConnection() {
  return useMutation({
    mutationFn: async (settings: { base_url: string; api_key: string; model: string }) => {
      const response = await fetch(settings.base_url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${settings.api_key}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: settings.model,
          messages: [
            { role: 'user', content: 'Say "Connection successful!" in one short sentence.' }
          ],
          max_tokens: 50,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      return data.choices?.[0]?.message?.content || 'Connection successful!';
    },
  });
}
