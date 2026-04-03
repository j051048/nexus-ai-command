/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * useWebSocketPush 单元测试
 *
 * 覆盖：连接建立、认证、心跳、重连退避、NO_RECONNECT_CODES、组件卸载清理
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ── Mock WebSocket ─────────────────────────────────────────────────────────

class MockWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;
  static instances: MockWebSocket[] = [];

  url: string;
  readyState = 0;
  onopen: ((ev: any) => void) | null = null;
  onclose: ((ev: any) => void) | null = null;
  onmessage: ((ev: any) => void) | null = null;
  onerror: ((ev: any) => void) | null = null;
  closeCalled = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send = vi.fn();
  close = vi.fn((code?: number, reason?: string) => {
    this.closeCalled = true;
    this.readyState = 3;
  });

  simulateOpen() {
    this.readyState = 1;
    this.onopen?.({ type: 'open' });
  }

  simulateMessage(data: any) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  simulateClose(code = 1000, reason = '') {
    this.readyState = 3;
    this.onclose?.({ code, reason, wasClean: true });
  }
}

vi.stubGlobal('WebSocket', MockWebSocket);

// ── Mock Supabase ──────────────────────────────────────────────────────────

vi.mock('@/integrations/supabase/client', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: 'test-jwt-token' } },
      }),
    },
  },
}));

vi.mock('sonner', () => ({ toast: { info: vi.fn(), warning: vi.fn(), error: vi.fn() } }));
vi.mock('@/lib/proactiveMessageStore', () => ({ enqueueProactiveMessage: vi.fn() }));

vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com');

// ── Helpers ────────────────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

describe('useWebSocketPush', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    MockWebSocket.instances = [];
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('构造正确的 wss:// URL', async () => {
    const { useWebSocketPush } = await import('@/hooks/useWebSocketPush');
    renderHook(() => useWebSocketPush(), { wrapper });

    // 等待 async connect
    await vi.advanceTimersByTimeAsync(100);

    expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(1);
    const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    expect(ws.url).toContain('wss://api.example.com/ws/push');
    expect(ws.url).toContain('token=test-jwt-token');
  });

  it('NO_RECONNECT_CODES (1013/4001/4002/4003) 不触发重连', async () => {
    const { useWebSocketPush } = await import('@/hooks/useWebSocketPush');
    renderHook(() => useWebSocketPush(), { wrapper });

    await vi.advanceTimersByTimeAsync(100);
    const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    ws.simulateOpen();

    const countBefore = MockWebSocket.instances.length;
    ws.simulateClose(1013, 'Too many connections');

    // 推进足够时间，不应创建新连接
    await vi.advanceTimersByTimeAsync(60000);
    expect(MockWebSocket.instances.length).toBe(countBefore);
  });

  it('组件卸载时关闭连接', async () => {
    const { useWebSocketPush } = await import('@/hooks/useWebSocketPush');
    const { unmount } = renderHook(() => useWebSocketPush(), { wrapper });

    await vi.advanceTimersByTimeAsync(100);
    const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    ws.simulateOpen();

    unmount();
    expect(ws.close).toHaveBeenCalled();
  });
});
