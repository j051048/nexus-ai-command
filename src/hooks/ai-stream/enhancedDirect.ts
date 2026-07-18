import { aiClient } from '@/api/aiClient';
import { supabase } from '@/integrations/supabase/client';
import { fetchBusinessContext } from '@/services/businessContext';
import { buildSystemPrompt, type UserProfile } from '@/services/agentPrompts';
import { parseAIResponseStream } from './protocol';

interface EnhancedDirectStreamOptions {
  chatMessages: Array<{ role: string; content: string }>;
  signal: AbortSignal;
  onUpdate?: (content: string, id: string) => void;
  agent?: string;
  onStatus: (status: string | undefined) => void;
}

/**
 * Optional browser fallback routed through the backend proxy.
 *
 * The feature is disabled by default at the caller. API credentials are read
 * only to verify tenant configuration and are never sent by the browser.
 */
export async function attemptEnhancedDirectStream({
  chatMessages,
  signal,
  onUpdate,
  agent,
  onStatus,
}: EnhancedDirectStreamOptions): Promise<boolean> {
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return false;

  const profileResponse = await aiClient.fetch<{
    success: boolean;
    data: { user?: Record<string, string | undefined> };
  }>('api/users/profile');
  const profile = profileResponse.data?.user;
  const orgId = profile?.organization_id;
  let settingsQuery = supabase
    .from('ai_settings')
    .select('base_url, api_key, model')
    .eq('user_id', user.id);
  if (orgId) settingsQuery = settingsQuery.eq('organization_id', orgId);
  const settingsResult = await settingsQuery.maybeSingle();
  const aiSettings = settingsResult.data as Record<string, unknown> | null;

  if (!aiSettings?.api_key || !aiSettings?.base_url) {
    throw new Error('请先在设置中心配置 AI API Key 和 Base URL');
  }

  const userProfile: UserProfile = {
    fullName: profile?.full_name || '未知用户',
    role: profile?.role || 'employee',
    department: profile?.department || undefined,
    jobTitle: profile?.job_title || undefined,
  };

  onStatus('正在加载业务数据...');
  const businessContext = await fetchBusinessContext(agent, user.id, userProfile.role);
  const systemPrompt = buildSystemPrompt(agent, userProfile, businessContext);
  const messagesWithContext = [{ role: 'system', content: systemPrompt }, ...chatMessages];

  onStatus('正在连接 AI 服务...');
  const response = await aiClient.stream('api/chat/proxy', {
    method: 'POST',
    body: JSON.stringify({
      model: 'deepseek-v4-flash',
      messages: messagesWithContext,
      stream: true,
    }),
    signal,
  });
  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    throw new Error(`AI 服务错误 (${response.status}): ${errorText.slice(0, 100) || '未知错误'}`);
  }
  if (!response.body) return false;

  onStatus(undefined);
  await parseAIResponseStream(response, { onUpdate });
  return true;
}
