/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * useContracts hooks 单元测试
 * 覆盖: useContracts, useContractDetail, useCreateContract,
 *       useUpdateContract, useDeleteContract
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ── Mocks ──────────────────────────────────────────────────────

const mockHttpGet = vi.fn();
const mockHttpPost = vi.fn();
const mockHttpPut = vi.fn();
vi.mock('@/lib/httpClient', () => ({
  httpClient: {
    get: (...a: unknown[]) => mockHttpGet(...a),
    post: (...a: unknown[]) => mockHttpPost(...a),
    put: (...a: unknown[]) => mockHttpPut(...a),
  },
}));

const mockAiFetch = vi.fn();
vi.mock('@/api/aiClient', () => ({
  aiClient: { fetch: (...a: unknown[]) => mockAiFetch(...a) },
}));

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

let mockAuth: any = { profile: { organization_id: 'org-1' } };
vi.mock('@/components/auth/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

// ── Helpers ────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

const CONTRACT = {
  id: 'ct-1', title: '测试合同', contract_number: 'CN-001',
  contract_type: 'sales', status: 'active', amount: 50000,
};

// ── Tests ──────────────────────────────────────────────────────

describe('useContracts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth = { profile: { organization_id: 'org-1' } };
  });

  describe('useContracts (列表)', () => {
    it('正常获取合同列表', async () => {
      mockHttpGet.mockResolvedValueOnce({ data: { contracts: [CONTRACT] } });
      const { useContracts } = await import('@/hooks/useContracts');
      const { result } = renderHook(() => useContracts(), { wrapper });
      await waitFor(() => expect(result.current.data).toBeDefined());
      expect(result.current.data).toHaveLength(1);
    });

    it('带筛选条件获取', async () => {
      mockHttpGet.mockResolvedValueOnce({ data: { contracts: [] } });
      const { useContracts } = await import('@/hooks/useContracts');
      renderHook(() => useContracts({ status: 'active', search: '测试' }), { wrapper });
      await waitFor(() => expect(mockHttpGet).toHaveBeenCalled());
      expect(mockHttpGet).toHaveBeenCalledWith(expect.stringContaining('status=active'));
    });

    it('orgId 缺失时不请求', async () => {
      mockAuth = { profile: null };
      const { useContracts } = await import('@/hooks/useContracts');
      renderHook(() => useContracts(), { wrapper });
      expect(mockHttpGet).not.toHaveBeenCalled();
    });

    it('API 返回非数组时防御处理', async () => {
      mockHttpGet.mockResolvedValueOnce({ data: { contracts: null } });
      const { useContracts } = await import('@/hooks/useContracts');
      const { result } = renderHook(() => useContracts(), { wrapper });
      await waitFor(() => expect(result.current.isFetching).toBe(false));
      expect(result.current.data).toEqual([]);
    });
  });

  describe('useContractDetail', () => {
    it('正常获取合同事件', async () => {
      const events = [{ id: 'e-1', event_type: 'created', description: '合同创建' }];
      mockHttpGet.mockResolvedValueOnce({ data: { events } });
      const { useContractDetail } = await import('@/hooks/useContracts');
      const { result } = renderHook(() => useContractDetail('ct-1'), { wrapper });
      await waitFor(() => expect(result.current.data).toBeDefined());
      expect(result.current.data).toHaveLength(1);
    });

    it('contractId 为 null 时不请求', async () => {
      const { useContractDetail } = await import('@/hooks/useContracts');
      renderHook(() => useContractDetail(null), { wrapper });
      expect(mockHttpGet).not.toHaveBeenCalled();
    });
  });

  describe('useCreateContract', () => {
    it('成功创建合同', async () => {
      mockHttpPost.mockResolvedValueOnce({ data: { contract: CONTRACT } });
      const { useCreateContract } = await import('@/hooks/useContracts');
      const { result } = renderHook(() => useCreateContract(), { wrapper });

      await act(async () => {
        result.current.mutate({ title: '新合同', contract_type: 'sales' });
      });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });
  });

  describe('useUpdateContract', () => {
    it('成功更新合同', async () => {
      mockHttpPut.mockResolvedValueOnce({ data: { contract: { ...CONTRACT, status: 'signed' } } });
      const { useUpdateContract } = await import('@/hooks/useContracts');
      const { result } = renderHook(() => useUpdateContract(), { wrapper });

      await act(async () => {
        result.current.mutate({ id: 'ct-1', updates: { status: 'signed' } });
      });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });
  });

  describe('useDeleteContract', () => {
    it('成功删除合同并显示 toast', async () => {
      mockAiFetch.mockResolvedValueOnce({ success: true });
      const { useDeleteContract } = await import('@/hooks/useContracts');
      const { toast } = await import('sonner');
      const { result } = renderHook(() => useDeleteContract(), { wrapper });

      await act(async () => {
        result.current.mutate('ct-1');
      });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(toast.success).toHaveBeenCalledWith('合同已删除');
    });

    it('删除失败显示错误 toast', async () => {
      mockAiFetch.mockRejectedValueOnce(new Error('权限不足'));
      const { useDeleteContract } = await import('@/hooks/useContracts');
      const { toast } = await import('sonner');
      const { result } = renderHook(() => useDeleteContract(), { wrapper });

      await act(async () => {
        result.current.mutate('ct-1');
      });
      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(toast.error).toHaveBeenCalled();
    });
  });
});
