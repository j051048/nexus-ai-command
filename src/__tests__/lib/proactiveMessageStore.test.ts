import { beforeEach, describe, expect, it } from 'vitest';
import { drainProactiveMessages, enqueueProactiveMessage, type ProactiveMessage } from '@/lib/proactiveMessageStore';

const message = (id: string, organizationId = 'a', userId = 'u'): ProactiveMessage => ({
  id, organizationId, userId, sessionId: 'default', title: '结果', message: id, receivedAt: new Date(),
});
beforeEach(() => { drainProactiveMessages('', ''); });

describe('proactive result queue', () => {
  it('never delivers another tenant or user result', () => {
    enqueueProactiveMessage(message('boundary-a'));
    enqueueProactiveMessage(message('boundary-b', 'b'));
    enqueueProactiveMessage(message('boundary-user', 'a', 'other'));
    expect(drainProactiveMessages('a', 'u').map(item => item.id)).toEqual(['boundary-a']);
    expect(drainProactiveMessages('b', 'u')).toEqual([]);
  });
  it('deduplicates events, not the shared default session', () => {
    enqueueProactiveMessage(message('one'));
    enqueueProactiveMessage(message('one'));
    enqueueProactiveMessage(message('two'));
    expect(drainProactiveMessages('a', 'u')).toHaveLength(2);
    enqueueProactiveMessage(message('one'));
    expect(drainProactiveMessages('a', 'u')).toEqual([]);
  });
  it('bounds queued results and rejects missing identity', () => {
    enqueueProactiveMessage(message('unscoped', ''));
    expect(drainProactiveMessages('a', 'u')).toEqual([]);
    for (let i = 0; i < 130; i++) enqueueProactiveMessage(message(`bounded-${i}`));
    expect(drainProactiveMessages('a', 'u')).toHaveLength(100);
  });
});
