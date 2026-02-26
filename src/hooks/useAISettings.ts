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
  { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash Preview (日常默认)' },
  { value: 'deepseek-v3', label: 'DeepSeek-V3 (推荐: 极速且聪明)' },
  { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (推荐: 查阅超大文档)' },
  { value: 'qwen-plus-latest', label: '通义千问 Plus (适合: 报告与邮件润色)' },
  { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet (高级: 修改代码与架构)' },
  { value: 'deepseek-reasoner', label: 'DeepSeek R1/Reasoner (高级: 深度数据排查与战略推演)' },
  { value: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro (实验: 最强多模态预览)' },
  { value: 'gpt-4o-mini', label: 'GPT-4o mini (快速稳定备选)' },
  { value: 'claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku (优质短文客服装)' },
  { value: 'o3-mini', label: 'o3-mini (复杂逻辑推演备选)' },
  { value: 'qwen-vl-plus', label: 'Qwen-VL-Plus (性价比视觉 OCR)' },
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

      const { data: profileData, error: profileError } = await sb.from('users')
        .select('organization_id')
        .eq('id', userId)
        .maybeSingle();

      if (profileError) throw new Error('获取用户信息失败: ' + profileError.message);
      
      if (!profileData || !profileData.organization_id) throw new Error('用户组织信息缺失，请联系管理员');

      const organizationId = profileData.organization_id as string;

      // Check if settings exist for THIS organization and user
      const { data: existing, error: checkError } = await sb
        .from('ai_settings')
        .select('id')
        .eq('user_id', userId)
        .eq('organization_id', organizationId)
        .maybeSingle();

      if (checkError) throw new Error(checkError.message);

      if (existing) {
        const { data, error } = await sb
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
        const { data, error } = await sb
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
