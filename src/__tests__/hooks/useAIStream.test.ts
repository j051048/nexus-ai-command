/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

// ─── Mock supabase ──────────────────────────────────────────

vi.mock('@/integrations/supabase/client', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: 'mock-token', user: { id: 'user-123' } } },
        error: null,
      }),
      getUser: vi.fn().mockResolvedValue({
        data: { user: { id: 'user-123' } },
      }),
    },
    from: vi.fn().mockReturnValue({
      select: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          maybeSingle: vi.fn().mockResolvedValue({
            data: { organization_id: 'org-1' },
            error: null,
          }),
        }),
      }),
      insert: vi.fn().mockReturnValue({
        select: vi.fn().mockReturnValue({
          single: vi.fn().mockResolvedValue({ data: { id: 'msg-1' }, error: null }),
        }),
      }),
    }),
  },
}));

// ─── Mock sonner ──────────────────────────────────────────

const mockToast = {
  error: vi.fn(),
  info: vi.fn(),
  success: vi.fn(),
};

vi.mock('sonner', () => ({
  toast: mockToast,
}));

// ─── Mock service modules ─────────────────────────────────

vi.mock('@/services/agentPrompts', () => ({
  buildSystemPrompt: vi.fn().mockReturnValue('mock system prompt'),
}));

vi.mock('@/services/businessContext', () => ({
  fetchBusinessContext: vi.fn().mockResolvedValue({ summary: 'mock context' }),
}));

// ─── Mock fetch ──────────────────────────────────────────

const mockFetchFn = vi.fn();

// ─── Mock import.meta.env ─────────────────────────────────

vi.stubEnv('VITE_API_BASE_URL', 'https://api.test.com');
vi.stubEnv('VITE_SUPABASE_URL', 'https://supabase.test.com');

// ─── 测试用例 ──────────────────────────────────────────────

describe('useAIStream', () => {
  // 增加超时到 15s 以支持三层重试逻辑测试
  vi.setConfig({ testTimeout: 15000 });
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchFn.mockReset();
    globalThis.fetch = mockFetchFn as typeof fetch;
    // Default: navigator.onLine = true
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('初始状态：isTyping=false, aiStatus=undefined, thinkingSteps 为空', async () => {
    const { useAIStream } = await import('@/hooks/useAIStream');
    const { result } = renderHook(() => useAIStream({ userId: 'user-123' }));

    expect(result.current.isTyping).toBe(false);
    expect(result.current.aiStatus).toBeUndefined();
    expect(result.current.thinkingSteps).toEqual([]);
    expect(result.current.isThinkingComplete).toBe(false);
  });

  it('返回 streamChat 和 stopStream 函数', async () => {
    const { useAIStream } = await import('@/hooks/useAIStream');
    const { result } = renderHook(() => useAIStream({ userId: 'user-123' }));

    expect(typeof result.current.streamChat).toBe('function');
    expect(typeof result.current.stopStream).toBe('function');
    expect(typeof result.current.clearThinkingSteps).toBe('function');
  });

  it('网络断开时抛出错误', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });

    const { useAIStream } = await import('@/hooks/useAIStream');
    const { result } = renderHook(() => useAIStream({ userId: 'user-123' }));

    const history: any[] = [];

    await expect(
      act(() => result.current.streamChat('你好', history))
    ).rejects.toThrow();

    // toast.error should have been called
    expect(mockToast.error).toHaveBeenCalled();
  });

  it('Tier 1a 成功时不触发后续 tier', async () => {
    // Tier 1a returns a successful SSE response
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"choices":[{"delta":{"content":"你好"}}]}\n\n'));
        controller.enqueue(encoder.encode('data: [DONE]\n\n'));
        controller.close();
      },
    });

    mockFetchFn.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'text/event-stream' }),
      body: stream,
    });

    const { useAIStream } = await import('@/hooks/useAIStream');
    const { result } = renderHook(() => useAIStream({ userId: 'user-123' }));

    const onUpdate = vi.fn();
    const history: any[] = [];

    await act(async () => {
      await result.current.streamChat('你好', history, undefined, onUpdate);
    });

    // Only Tier 1a was called (one fetch call)
    expect(mockFetchFn).toHaveBeenCalledTimes(1);
    expect(mockFetchFn.mock.calls[0][0]).toBe('https://api.test.com/api/chat');
    // onUpdate should have been called with the streamed content
    expect(onUpdate).toHaveBeenCalledWith('你好', expect.any(String));
  });

  it('三层全部失败时 isTyping 重置为 false', async () => {
    // All tiers fail with network error
    mockFetchFn.mockRejectedValue(new Error('Failed to fetch'));

    const { useAIStream } = await import('@/hooks/useAIStream');
    const { result } = renderHook(() => useAIStream({ userId: 'user-123' }));

    const history: any[] = [];
    const onUpdate = vi.fn();

    // 应使用 async act
    await act(async () => {
      try {
        await result.current.streamChat('测试', history, undefined, onUpdate);
      } catch (e) {
        // Expected
      }
    });

    // isTyping should be reset to false after failure
    // 使用 waitFor 确保异步状态已经同步到 hook 的 result 中
    await waitFor(() => expect(result.current.isTyping).toBe(false), { timeout: 3000 });
  });
});
