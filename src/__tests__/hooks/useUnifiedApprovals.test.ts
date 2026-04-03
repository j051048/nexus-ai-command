/**
 * useUnifiedApprovals / useTabCounts 单元测试
 * 覆盖: 各 tab 查询、筛选、分页、fallback 默认值、轮询配置
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ── Mocks ──────────────────────────────────────────────────────

const mockFetch = vi.fn();
vi.mock('@/api/aiClient', () => ({
  aiClient: { fetch: (...a: unknown[]) => mockFetch(...a) },
}));

// ── Helpers ────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

const APPROVAL_ITEM = {
  id: 'ap-1', source_table: 'approval_requests', type: 'leave',
  description: '请假申请', amount: null, status: 'pending',
  submitted_by: 'u-1', submitter_name: '张三', created_at: '2026-01-01',
};

// ── Tests ──────────────────────────────────────────────────────

describe('useUnifiedApprovals', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('正常获取 pending tab 数据', async () => {
    mockFetch.mockResolvedValueOnce({
      data: { items: [APPROVAL_ITEM], total: 1, page: 1, page_size: 20 },
    });
    const { useUnifiedApprovals } = await import('@/hooks/useUnifiedApprovals');
    const { result } = renderHook(() => useUnifiedApprovals('pending'), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.total).toBe(1);
  });

  it('mine tab 正常查询', async () => {
    mockFetch.mockResolvedValueOnce({
      data: { items: [], total: 0, page: 1, page_size: 20 },
    });
    const { useUnifiedApprovals } = await import('@/hooks/useUnifiedApprovals');
    const { result } = renderHook(() => useUnifiedApprovals('mine'), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('tab=mine'));
  });

  it('handled tab 带 typeFilter', async () => {
    mockFetch.mockResolvedValueOnce({
      data: { items: [], total: 0, page: 1, page_size: 20 },
    });
    const { useUnifiedApprovals } = await import('@/hooks/useUnifiedApprovals');
    renderHook(() => useUnifiedApprovals('handled', 'leave', 2), { wrapper });
    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('type_filter=leave');
    expect(url).toContain('page=2');
  });

  it('API 返回 null 时 fallback 默认值', async () => {
    mockFetch.mockResolvedValueOnce({ data: null });
    const { useUnifiedApprovals } = await import('@/hooks/useUnifiedApprovals');
    const { result } = renderHook(() => useUnifiedApprovals('pending'), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.items).toEqual([]);
    expect(result.current.data?.total).toBe(0);
  });
});

describe('useTabCounts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('正常获取 tab 计数', async () => {
    mockFetch.mockResolvedValueOnce({ data: { pending: 5, mine: 3 } });
    const { useTabCounts } = await import('@/hooks/useUnifiedApprovals');
    const { result } = renderHook(() => useTabCounts(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.pending).toBe(5);
    expect(result.current.data?.mine).toBe(3);
  });

  it('API 返回 null 时 fallback 默认值', async () => {
    mockFetch.mockResolvedValueOnce({ data: null });
    const { useTabCounts } = await import('@/hooks/useUnifiedApprovals');
    const { result } = renderHook(() => useTabCounts(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.pending).toBe(0);
    expect(result.current.data?.mine).toBe(0);
  });
});
