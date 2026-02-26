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
  { value: 'gpt-4o', label: 'GPT-4o (稳定推荐)' },
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo (快速)' },
  { value: 'claude-3-opus-20240229', label: 'Claude 3 Opus' },
  { value: 'claude-3-sonnet-20240229', label: 'Claude 3 Sonnet' },
  { value: 'google/gemini-pro', label: 'Gemini Pro' },
  { value: 'google/gemini-1.5-pro-latest', label: 'Gemini 1.5 Pro' },
  { value: 'google/gemini-3-pro-preview', label: 'Gemini 3 Pro Preview (实验性)' },
  { value: 'custom', label: '自定义模型...' },
];

export function useAISettings() {
  const { user, profile } = useAuth();

  return useQuery({
    queryKey: ['ai-settings', profile?.organization_id],
    queryFn: async () => {
      if (!user || !profile) return null;

      const { data, error } = await supabase
        .from('ai_settings')
        .select('*')
        .eq('user_id', user.id)
        .eq('organization_id', profile.organization_id)
        .maybeSingle();

      if (error) {
        throw new Error(error.message || '获取配置失败');
      }
      return data as AISettings | null;
    },
    enabled: !!user && !!profile,
  });
}

export function useSaveAISettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (settings: { base_url: string; api_key: string | null; model: string }) => {
      // 直接从 Supabase 实时获取当前会话，不依赖 React 状态/闭包
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.user) throw new Error('未登录，请重新登录');

      const userId = session.user.id;

      const { data: profileData, error: profileError } = await supabase.from('users')
        .select('organization_id')
        .eq('id', userId)
        .maybeSingle();

      if (profileError) throw new Error('获取用户信息失败: ' + profileError.message);
      if (!profileData?.organization_id) throw new Error('用户组织信息缺失，请联系管理员');

      const organizationId = profileData.organization_id as string;

      // Check if settings exist for THIS organization and user
      const { data: existing, error: checkError } = await supabase
        .from('ai_settings')
        .select('id')
        .eq('user_id', userId)
        .eq('organization_id', organizationId)
        .maybeSingle();

      if (checkError) throw new Error(checkError.message);

      if (existing) {
        const { data, error } = await supabase
          .from('ai_settings')
          .update({
            base_url: settings.base_url,
            api_key: settings.api_key,
            model: settings.model,
            updated_at: new Date().toISOString(),
          })
          .eq('id', existing.id)
          .select()
          .single();

        if (error) throw new Error(error.message);
        return data as AISettings;
      } else {
        const { data, error } = await supabase
          .from('ai_settings')
          .insert({
            user_id: userId,
            organization_id: organizationId,
            base_url: settings.base_url,
            api_key: settings.api_key,
            model: settings.model,
          })
          .select()
          .single();

        if (error) throw new Error(error.message);
        return data as AISettings;
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
      // Normalize URL: Ensure it ends with /chat/completions if not present
      let url = settings.base_url.replace(/\/$/, ''); // Remove trailing slash
      if (!url.endsWith('/chat/completions')) {
        if (url.endsWith('/v1')) {
          url += '/chat/completions';
        } else {
          // If user just input https://proxy.flydao.top, logic might be ambiguous, 
          // but standard OpenAI client behavior usually expects base_url to be the root.
          // However, for this low-code UI, let's try to be smart.
          // If it doesn't look like a full endpoint, append standard path.
          // Only do this if it contains 'proxy' or 'gateway' to be safe, or just append /v1/chat/completions as a guess?
          // Safer bet: If it doesn't end in /v1, assume it needs /v1/chat/completions
          url += '/v1/chat/completions';
        }
      }

      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.log('Testing connection to:', url);
      }

      const response = await fetch(url, {
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
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errorJson = JSON.parse(errorText);
          if (errorJson.error?.message) {
            errorMessage += ` - ${errorJson.error.message}`;
          }
        } catch (e) {
          // ignore JSON parse error
          if (errorText.length < 100) errorMessage += ` - ${errorText}`;
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      return data.choices?.[0]?.message?.content || 'Connection successful!';
    },
  });
}
