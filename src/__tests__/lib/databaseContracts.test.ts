import { describe, expect, it, vi } from 'vitest';
import type { Tables } from '@/integrations/supabase/types';
import { normalizeAuthRole } from '@/lib/userRoles';
import { toDocument } from '@/components/documents/documentContract';
import { loadPersistedProactiveMessages, toProactiveMessage } from '@/components/ai/chat/persistedProactiveMessages';

const db = vi.hoisted(() => ({ from: vi.fn() }));
vi.mock('@/integrations/supabase/client', () => ({ supabase: db }));
const row: Tables<'chat_messages'> = {
  id: 'm1', user_id: 'u', organization_id: 'a', role: 'assistant', session_id: 'default',
  content: '完整的定时任务结果', agent: null, metadata: { source: 'scheduled_task', task_name: '周报' },
  created_at: '2026-09-14T00:00:00Z',
};

describe('database-backed UI contracts', () => {
  it.each(['pending_boss', 'super_admin', '', null, {}, 'owner'])('unknown role %s never grants privileges', value => {
    expect(normalizeAuthRole(value)).toBe('employee');
  });
  it('normalizes founder without conflating organization and platform admin', () => {
    expect(normalizeAuthRole('founder')).toBe('boss');
    expect(normalizeAuthRole('admin')).toBe('admin');
  });
  it('restores persisted results only for the exact tenant and user', () => {
    expect(toProactiveMessage(row, 'a', 'u')).toMatchObject({ id: 'm1', content: row.content, agent: '周报' });
    expect(toProactiveMessage({ ...row, metadata: { source: 'proactive', event_id: 'shared-event' } }, 'a', 'u'))
      .toMatchObject({ id: 'proactive-shared-event' });
    expect(toProactiveMessage(row, 'b', 'u')).toBeNull();
    expect(toProactiveMessage(row, 'a', 'other')).toBeNull();
    for (const patch of [{ role: 'user' }, { created_at: 'invalid' }, { metadata: {} }, { content: '' }]) {
      expect(toProactiveMessage({ ...row, ...patch }, 'a', 'u')).toBeNull();
    }
  });
  it('uses the actual persistence table, scopes both identities and honors cancellation', async () => {
    const query = { select: vi.fn(), eq: vi.fn(), in: vi.fn(), order: vi.fn(), limit: vi.fn(), abortSignal: vi.fn() };
    for (const method of Object.values(query)) method.mockReturnValue(query);
    query.abortSignal.mockResolvedValue({ data: [row], error: null });
    db.from.mockReturnValue(query);
    const signal = new AbortController().signal;
    expect(await loadPersistedProactiveMessages('a', 'u', signal)).toHaveLength(1);
    expect(db.from).toHaveBeenCalledWith('chat_messages');
    expect(query.eq).toHaveBeenCalledWith('organization_id', 'a');
    expect(query.eq).toHaveBeenCalledWith('user_id', 'u');
    expect(query.abortSignal).toHaveBeenCalledWith(signal);
    query.abortSignal.mockResolvedValue({ data: null, error: new Error('offline') });
    await expect(loadPersistedProactiveMessages('a', 'u', signal)).rejects.toThrow('offline');
  });
  it('never labels unknown indexing state as completed and tolerates malformed legacy extraction', () => {
    const document = { id: 'doc', name: '方案', status: null, doc_type: 'unknown', extracted_data: '{broken', created_at: null } as Tables<'documents'>;
    expect(toDocument(document)).toMatchObject({ doc_type: 'other', status: 'processing', extracted_data: {} });
    expect(toDocument({ ...document, status: 'ready' }).status).toBe('completed');
    expect(toDocument({ ...document, status: 'failed' }).status).toBe('error');
  });
});
