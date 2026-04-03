import { describe, it, expect, beforeEach, vi } from 'vitest';
import { offlineQueue } from '@/services/offlineQueue';
import type { QueuedOperation } from '@/services/offlineQueue';

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
        { id: '1', url: '/test1', method: 'POST', retries: 0, timestamp: Date.now() },
        { id: '2', url: '/test2', method: 'GET', retries: 0, timestamp: Date.now() },
      ];

      // We bypass the actual DB calls by mocking the internal methods
      const getAllSpy = vi.spyOn(offlineQueue, 'getAll').mockResolvedValue(mockOps);
      const dequeueSpy = vi.spyOn(offlineQueue, 'dequeue').mockResolvedValue(undefined);

      vi.mocked(global.fetch).mockResolvedValue({ ok: true, status: 200 } as Response);

      const result = await offlineQueue.replay();

      expect(getAllSpy).toHaveBeenCalled();
      expect(global.fetch).toHaveBeenCalledTimes(2);
      expect(dequeueSpy).toHaveBeenCalledTimes(2);
      expect(result.success).toBe(2);
    });

    it('should handle retries on failure', async () => {
      const mockOps: QueuedOperation[] = [
        { id: 'fail-1', url: '/fail', method: 'POST', retries: 0, timestamp: Date.now() },
      ];

      vi.spyOn(offlineQueue, 'getAll').mockResolvedValue(mockOps);
      // @ts-expect-error - access private method for mocking
      const updateRetriesSpy = vi.spyOn(offlineQueue, 'updateRetries').mockResolvedValue(undefined);

      vi.mocked(global.fetch).mockResolvedValue({ ok: false, status: 500 } as Response);

      const result = await offlineQueue.replay();

      expect(result.failed).toBe(1);
      expect(updateRetriesSpy).toHaveBeenCalledWith('fail-1', 1);
    });
  });
});
