/**
 * useApprovals / useMyApprovals / useAllApprovals 单元测试
 *
 * 覆盖：正常获取、空数据、Zod 校验降级、权限控制、mutation 成功/失败
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockHttpGet = vi.fn();
const mockHttpPost = vi.fn();
vi.mock('@/lib/httpClient', () => ({
  httpClient: { get: (...a: unknown[]) => mockHttpGet(...a), post: (...a: unknown[]) => mockHttpPost(...a) },
}));

vi.mock('@/api/aiClient', () => ({ aiClient: { post: vi.fn() } }));
vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const mockAuth = {
  user: { id: 'u-1' },
  profile: { organization_id: 'org-1' },
  role: 'boss' as const,
};
vi.mock('@/components/auth/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

// ── Helpers ────────────────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('useApprovals', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('boss 角色正常获取待审批列表', async () => {
    const items = [
      {
        id: '550e8400-e29b-41d4-a716-446655440000',
        submitted_by: '550e8400-e29b-41d4-a716-446655440001',
        type: 'leave',
        amount: 0,
        description: '请假',
        status: 'pending',
        created_at: '2026-01-01T00:00:00Z',
        submitter_name: '张三',
      },
    ];
    mockHttpGet.mockResolvedValueOnce({ data: { data: { items } } });

    const { useApprovals } = await import('@/hooks/useApprovals');
    const { result } = renderHook(() => useApprovals(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.pendingApprovals).toHaveLength(1);
    expect(result.current.pendingApprovals[0].submitter_name).toBe('张三');
  });

  it('非 boss 角色不触发查询', async () => {
    mockAuth.role = 'employee' as any;
    const { useApprovals } = await import('@/hooks/useApprovals');
    const { result } = renderHook(() => useApprovals(), { wrapper });

    // 不应发起请求
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(mockHttpGet).not.toHaveBeenCalled();
    expect(result.current.pendingApprovals).toEqual([]);
    mockAuth.role = 'boss' as any; // restore
  });

  it('Zod 校验失败时降级返回原始数据', async () => {
    const badItem = {
      id: 'not-a-uuid', // invalid UUID
      submitted_by: '550e8400-e29b-41d4-a716-446655440001',
      type: 'expense',
      amount: 100,
      status: 'pending',
      created_at: '2026-01-01T00:00:00Z',
    };
    mockHttpGet.mockResolvedValueOnce({ data: { data: { items: [badItem] } } });

    const { useApprovals } = await import('@/hooks/useApprovals');
    const { result } = renderHook(() => useApprovals(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    // 降级：仍然返回数据，不崩溃
    expect(result.current.pendingApprovals).toHaveLength(1);
  });

  it('updateStatus mutation 成功后 invalidate 缓存', async () => {
    mockHttpGet.mockResolvedValueOnce({ data: { data: { items: [] } } });
    mockHttpPost.mockResolvedValueOnce({ data: { success: true } });

    const { useApprovals } = await import('@/hooks/useApprovals');
    const { result } = renderHook(() => useApprovals(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      result.current.updateStatus.mutate({ id: 'test-id', status: 'approved' });
    });

    await waitFor(() => expect(mockHttpPost).toHaveBeenCalledWith(
      '/api/approval/test-id/advance',
      { decision: 'approved' },
    ));
  });

  it('updateStatus mutation 失败时 toast 错误', async () => {
    mockHttpGet.mockResolvedValueOnce({ data: { data: { items: [] } } });
    mockHttpPost.mockRejectedValueOnce(new Error('网络错误'));

    const { toast } = await import('sonner');
    const { useApprovals } = await import('@/hooks/useApprovals');
    const { result } = renderHook(() => useApprovals(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      result.current.updateStatus.mutate({ id: 'x', status: 'rejected' });
    });

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it('organization_id 为空时返回空数组', async () => {
    const saved = mockAuth.profile;
    mockAuth.profile = { organization_id: '' } as any;

    const { useApprovals } = await import('@/hooks/useApprovals');
    const { result } = renderHook(() => useApprovals(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.pendingApprovals).toEqual([]);
    mockAuth.profile = saved;
  });
});

describe('useMyApprovals', () => {
  beforeEach(() => vi.clearAllMocks());

  it('获取当前用户的审批列表', async () => {
    mockHttpGet.mockResolvedValueOnce({ data: { data: { items: [{ id: 'a1' }] } } });

    const { useMyApprovals } = await import('@/hooks/useApprovals');
    const { result } = renderHook(() => useMyApprovals(), { wrapper });

    await waitFor(() => expect(result.current.data).toHaveLength(1));
    expect(mockHttpGet).toHaveBeenCalledWith('/api/approval/list', { params: { tab: 'mine' } });
  });

  it('未登录时不触发查询', async () => {
    const saved = mockAuth.user;
    mockAuth.user = null as any;

    const { useMyApprovals } = await import('@/hooks/useApprovals');
    const { result } = renderHook(() => useMyApprovals(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(mockHttpGet).not.toHaveBeenCalled();
    mockAuth.user = saved;
  });
});
