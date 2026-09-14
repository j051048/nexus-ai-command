import { supabase } from '@/integrations/supabase/client';
import type { Tables } from '@/integrations/supabase/types';
import type { AIMessage } from '@/types/nexus';

type ChatRow = Tables<'chat_messages'>;
const SOURCES = ['proactive', 'scheduled_task', 'smart_reminder'];

export function toProactiveMessage(row: ChatRow, orgId: string, userId: string): AIMessage | null {
  if (row.organization_id !== orgId || row.user_id !== userId || row.role !== 'assistant') return null;
  const meta = row.metadata;
  if (!meta || typeof meta !== 'object' || Array.isArray(meta) || typeof meta.source !== 'string' || !SOURCES.includes(meta.source)) return null;
  if (!row.content.trim() || !row.created_at || !Number.isFinite(Date.parse(row.created_at))) return null;
  return {
    id: typeof meta.event_id === 'string' ? `proactive-${meta.event_id}` : row.id,
    role: 'assistant',
    content: row.content,
    timestamp: new Date(row.created_at),
    agent: typeof meta.task_name === 'string' ? meta.task_name : (row.agent || '主动推送'),
    isProactive: true,
  };
}

export async function loadPersistedProactiveMessages(orgId: string, userId: string, signal: AbortSignal): Promise<AIMessage[]> {
  if (!orgId || !userId) throw new Error('企业身份尚未就绪');
  // The producer persists full results in chat_messages, not a separate proactive table.
  const { data, error } = await supabase.from('chat_messages').select('*')
    .eq('organization_id', orgId).eq('user_id', userId).eq('role', 'assistant')
    .in('metadata->>source', SOURCES).order('created_at', { ascending: false })
    .limit(20).abortSignal(signal);
  if (error) throw error;
  return (data || []).reverse().flatMap(row => {
    const message = toProactiveMessage(row, orgId, userId);
    return message ? [message] : [];
  });
}
