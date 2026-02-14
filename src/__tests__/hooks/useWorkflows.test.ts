import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ─── Mock supabase ──────────────────────────────────────────

vi.mock('@/integrations/supabase/client', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: 'mock-token' } },
      }),
    },
  },
}));

// ─── Mock fetch ──────────────────────────────────────────────

const mockWorkflows = [
  {
    id: '1',
    name: '请假审批',
    description: '员工请假审批流程',
    approval_type: 'leave',
    definition: { steps: [], conditions: [] },
    is_active: true,
    is_default: false,
    version: 1,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: '2',
    name: '报销审批',
    description: '员工报销审批流程',
    approval_type: 'expense',
    definition: { steps: [], conditions: [] },
    is_active: true,
    is_default: true,
    version: 1,
    created_at: '2025-01-02T00:00:00Z',
    updated_at: '2025-01-02T00:00:00Z',
  },
];

// ─── 测试辅助 ──────────────────────────────────────────────

const mockFetchFn = vi.fn();

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

// ─── 测试用例 ──────────────────────────────────────────────

describe('useWorkflows', () => {
  beforeEach(() => {
    mockFetchFn.mockReset();
    global.fetch = mockFetchFn;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('成功获取工作流列表', async () => {
    mockFetchFn.mockResolvedValue({
      ok: true,
      json: async () => ({ data: mockWorkflows }),
    });

    const { useWorkflows } = await import('@/hooks/useWorkflows');
    const { result } = renderHook(() => useWorkflows(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(2);
    expect(result.current.data![0].name).toBe('请假审批');
    expect(result.current.data![1].approval_type).toBe('expense');
  });

  it('API 失败时返回错误', async () => {
    mockFetchFn.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: '服务器内部错误' }),
    });

    const { useWorkflows } = await import('@/hooks/useWorkflows');
    const { result } = renderHook(() => useWorkflows(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });

  it('请求包含 Authorization header', async () => {
    mockFetchFn.mockResolvedValue({
      ok: true,
      json: async () => ({ data: [] }),
    });

    const { useWorkflows } = await import('@/hooks/useWorkflows');
    renderHook(() => useWorkflows(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(mockFetchFn).toHaveBeenCalled());

    const callArgs = mockFetchFn.mock.calls[0];
    expect(callArgs[1].headers).toHaveProperty('Authorization', 'Bearer mock-token');
  });

  it('useWorkflow 使用正确的 ID 获取单个工作流', async () => {
    mockFetchFn.mockResolvedValue({
      ok: true,
      json: async () => ({ data: mockWorkflows[0] }),
    });

    const { useWorkflow } = await import('@/hooks/useWorkflows');
    const { result } = renderHook(() => useWorkflow('1'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.name).toBe('请假审批');
  });

  it('useWorkflow 当 id 为空时不发起请求', async () => {
    const { useWorkflow } = await import('@/hooks/useWorkflows');
    const { result } = renderHook(() => useWorkflow(undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockFetchFn).not.toHaveBeenCalled();
  });
});
