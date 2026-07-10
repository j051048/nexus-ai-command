import { describe, it, expect, beforeEach, vi } from 'vitest';
import { offlineQueue } from '@/services/offlineQueue';
import type { QueuedOperation } from '@/services/offlineQueue';

const identity = { organizationId: 'org-1', userId: 'user-1', sessionId: 'session-1' };

function queuedOperation(overrides: Partial<QueuedOperation> = {}): QueuedOperation {
  return {
    id: '1',
    url: '/api/test',
    method: 'POST',
    retries: 0,
    timestamp: Date.now(),
    organizationId: identity.organizationId,
    userId: identity.userId,
    sessionId: identity.sessionId,
    identityKey: 'org-1:user-1:session-1',
    idempotencyKey: 'idem-1',
    state: 'pending',
    ...overrides,
  };
}

describe('OfflineQueue Service (Logic Only)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();

    // Stub IndexedDB to prevent init failure
    vi.stubGlobal('indexedDB', {
      open: vi.fn().mockReturnValue({}),
    });
  });

  it('should have basic methods defined', () => {
    expect(offlineQueue.enqueue).toBeDefined();
    expect(offlineQueue.replay).toBeDefined();
    expect(offlineQueue.dequeue).toBeDefined();
  });

  describe('replay logic simulation', () => {
    it('should iterate over operations and call fetch', async () => {
      const mockOps: QueuedOperation[] = [
        queuedOperation({ id: '1', url: '/api/test1', method: 'POST' }),
        queuedOperation({ id: '2', url: '/api/test2', method: 'GET', idempotencyKey: 'idem-2' }),
      ];

      // We bypass the actual DB calls by mocking the internal methods
      const getAllSpy = vi.spyOn(offlineQueue, 'getAll').mockResolvedValue(mockOps);
      const dequeueSpy = vi.spyOn(offlineQueue, 'dequeue').mockResolvedValue(undefined);

      vi.mocked(global.fetch).mockResolvedValue({ ok: true, status: 200 } as Response);

      const result = await offlineQueue.replay({ identity });

      expect(getAllSpy).toHaveBeenCalled();
      expect(global.fetch).toHaveBeenCalledTimes(2);
      expect(dequeueSpy).toHaveBeenCalledTimes(2);
      expect(result.success).toBe(2);
    });

    it('should handle retries on failure', async () => {
      const mockOps: QueuedOperation[] = [
        queuedOperation({ id: 'fail-1', url: '/api/fail' }),
      ];

      vi.spyOn(offlineQueue, 'getAll').mockResolvedValue(mockOps);
      const updateSpy = vi
        .spyOn(
          offlineQueue as unknown as {
            update: (id: string, patch: Partial<QueuedOperation>) => Promise<void>;
          },
          'update',
        )
        .mockResolvedValue(undefined);

      vi.mocked(global.fetch).mockResolvedValue({ ok: false, status: 500 } as Response);

      const result = await offlineQueue.replay({ identity });

      expect(result.failed).toBe(1);
      expect(updateSpy).toHaveBeenCalledWith('fail-1', {
        retries: 1,
        lastError: 'Retryable server response (500)',
      });
    });

    it('keeps authorization failures blocked instead of deleting them', async () => {
      vi.spyOn(offlineQueue, 'getAll').mockResolvedValue([
        queuedOperation({ id: 'auth-fail' }),
      ]);
      const dequeueSpy = vi.spyOn(offlineQueue, 'dequeue').mockResolvedValue(undefined);
      const updateSpy = vi
        .spyOn(
          offlineQueue as unknown as {
            update: (id: string, patch: Partial<QueuedOperation>) => Promise<void>;
          },
          'update',
        )
        .mockResolvedValue(undefined);
      vi.mocked(global.fetch).mockResolvedValue({ ok: false, status: 403 } as Response);

      const result = await offlineQueue.replay({ identity });

      expect(result.blocked).toBe(1);
      expect(dequeueSpy).not.toHaveBeenCalled();
      expect(updateSpy).toHaveBeenCalledWith('auth-fail', {
        state: 'blocked',
        lastError: 'Authorization rejected (403)',
      });
    });
  });
});
