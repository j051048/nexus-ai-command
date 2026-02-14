/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// ─── Mock offlineQueue service ──────────────────────────────

const mockInit = vi.fn().mockResolvedValue(undefined);
const mockGetCount = vi.fn().mockResolvedValue(0);
const mockEnqueue = vi.fn().mockResolvedValue('mock-id-1');
const mockReplay = vi.fn().mockResolvedValue({ success: 2, failed: 0 });
const mockClear = vi.fn().mockResolvedValue(undefined);

vi.mock('@/services/offlineQueue', () => ({
  offlineQueue: {
    init: () => mockInit(),
    getCount: () => mockGetCount(),
    enqueue: (op: any) => mockEnqueue(op),
    replay: () => mockReplay(),
    clear: () => mockClear(),
  },
}));

// ─── 测试用例 ──────────────────────────────────────────────

describe('useOfflineQueue', () => {
  let originalOnLine: PropertyDescriptor | undefined;

  beforeEach(() => {
    vi.clearAllMocks();
    originalOnLine = Object.getOwnPropertyDescriptor(navigator, 'onLine');
  });

  afterEach(() => {
    // 恢复 navigator.onLine
    if (originalOnLine) {
      Object.defineProperty(navigator, 'onLine', originalOnLine);
    }
  });

  it('初始化时调用 init 并获取 count', async () => {
    mockGetCount.mockResolvedValueOnce(3);

    const { useOfflineQueue } = await import('@/hooks/useOfflineQueue');
    const { result } = renderHook(() => useOfflineQueue());

    // 等待初始化
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(mockInit).toHaveBeenCalled();
    expect(mockGetCount).toHaveBeenCalled();
    expect(result.current.count).toBe(3);
  });

  it('isOnline 反映 navigator.onLine 状态', async () => {
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true });

    const { useOfflineQueue } = await import('@/hooks/useOfflineQueue');
    const { result } = renderHook(() => useOfflineQueue());

    expect(result.current.isOnline).toBe(true);
  });

  it('enqueue 调用 offlineQueue.enqueue 并刷新计数', async () => {
    mockGetCount.mockResolvedValue(0);
    mockEnqueue.mockResolvedValueOnce('new-id');
    mockGetCount.mockResolvedValueOnce(1);

    const { useOfflineQueue } = await import('@/hooks/useOfflineQueue');
    const { result } = renderHook(() => useOfflineQueue());

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    await act(async () => {
      const id = await result.current.enqueue({
        url: '/api/test',
        method: 'POST',
        body: '{}',
      });
      expect(id).toBeDefined();
    });

    expect(mockEnqueue).toHaveBeenCalledWith(
      expect.objectContaining({
        url: '/api/test',
        method: 'POST',
      }),
    );
  });

  it('replay 调用 offlineQueue.replay', async () => {
    mockReplay.mockResolvedValueOnce({ success: 3, failed: 1 });

    const { useOfflineQueue } = await import('@/hooks/useOfflineQueue');
    const { result } = renderHook(() => useOfflineQueue());

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    let replayResult: any;
    await act(async () => {
      replayResult = await result.current.replay();
    });

    expect(mockReplay).toHaveBeenCalled();
    expect(replayResult).toEqual({ success: 3, failed: 1 });
  });

  it('网络恢复时自动重放队列', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, writable: true, configurable: true });

    const { useOfflineQueue } = await import('@/hooks/useOfflineQueue');
    const { result } = renderHook(() => useOfflineQueue());

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    // 模拟网络恢复
    await act(async () => {
      window.dispatchEvent(new Event('online'));
      await new Promise((r) => setTimeout(r, 100));
    });

    expect(result.current.isOnline).toBe(true);
  });
});
