/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * useCRM hooks 单元测试
 * 覆盖: useCustomers, useCustomer, useCreateCustomer, useUpdateCustomer,
 *       useDeleteCustomer, useCustomerContacts, useCustomerTimeline,
 *       useCustomerStats, useCreateContact, useCreateActivity
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ── Mocks ──────────────────────────────────────────────────────

const mockFetch = vi.fn();
vi.mock('@/api/aiClient', () => ({
  aiClient: { fetch: (...a: unknown[]) => mockFetch(...a) },
}));

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

// ── Helpers ────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

const CUSTOMER = {
  id: 'c-1', organization_id: 'org-1', name: '测试客户',
  company: 'Test Corp', industry: 'tech', stage: 'prospect',
  source: 'web', estimated_value: 100000, assigned_to: null,
  tags: [], metadata: {}, created_at: '2026-01-01', updated_at: '2026-01-01',
};

// ── Tests ──────────────────────────────────────────────────────

describe('useCRM', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useCustomers', () => {
    it('正常获取客户列表（分页）', async () => {
      mockFetch.mockResolvedValueOnce({
        success: true, data: [CUSTOMER], total: 1,
      });
      const { useCustomers } = await import('@/hooks/useCRM');
      const { result } = renderHook(() => useCustomers(), { wrapper });
      await waitFor(() => expect(result.current.data).toBeDefined());
      expect(result.current.data?.pages[0].data).toHaveLength(1);
    });

    it('带筛选条件获取客户', async () => {
      mockFetch.mockResolvedValueOnce({ success: true, data: [], total: 0 });
      const { useCustomers } = await import('@/hooks/useCRM');
      const { result } = renderHook(
        () => useCustomers({ stage: 'prospect', search: 'test' }),
        { wrapper },
      );
      await waitFor(() => expect(result.current.isFetching).toBe(false));
      expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('stage=prospect'));
    });
  });

  describe('useCustomer', () => {
    it('正常获取单个客户', async () => {
      mockFetch.mockResolvedValueOnce({
        success: true, data: { customer: CUSTOMER },
      });
      const { useCustomer } = await import('@/hooks/useCRM');
      const { result } = renderHook(() => useCustomer('c-1'), { wrapper });
      await waitFor(() => expect(result.current.data).toBeDefined());
      expect(result.current.data?.name).toBe('测试客户');
    });

    it('id 为 null 时不请求', async () => {
      const { useCustomer } = await import('@/hooks/useCRM');
      const { result } = renderHook(() => useCustomer(null), { wrapper });
      expect(result.current.isFetching).toBe(false);
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('useCreateCustomer', () => {
    it('成功创建客户并显示 toast', async () => {
      mockFetch.mockResolvedValueOnce({
        success: true, data: { customer: CUSTOMER },
      });
      const { useCreateCustomer } = await import('@/hooks/useCRM');
      const { toast } = await import('sonner');
      const { result } = renderHook(() => useCreateCustomer(), { wrapper });

      await act(async () => {
        result.current.mutate({ name: '新客户', company: 'New Corp' } as any);
      });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(toast.success).toHaveBeenCalledWith('客户创建成功');
    });

    it('创建失败显示错误 toast', async () => {
      mockFetch.mockRejectedValueOnce(new Error('网络错误'));
      const { useCreateCustomer } = await import('@/hooks/useCRM');
      const { toast } = await import('sonner');
      const { result } = renderHook(() => useCreateCustomer(), { wrapper });

      await act(async () => {
        result.current.mutate({ name: '失败' } as any);
      });
      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(toast.error).toHaveBeenCalled();
    });
  });

  describe('useUpdateCustomer', () => {
    it('成功更新客户', async () => {
      mockFetch.mockResolvedValueOnce({
        success: true, data: { customer: { ...CUSTOMER, name: '更新后' } },
      });
      const { useUpdateCustomer } = await import('@/hooks/useCRM');
      const { toast } = await import('sonner');
      const { result } = renderHook(() => useUpdateCustomer(), { wrapper });

      await act(async () => {
        result.current.mutate({ id: 'c-1', data: { name: '更新后' } });
      });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(toast.success).toHaveBeenCalledWith('客户信息已更新');
    });
  });

  describe('useDeleteCustomer', () => {
    it('成功删除客户', async () => {
      mockFetch.mockResolvedValueOnce({ success: true });
      const { useDeleteCustomer } = await import('@/hooks/useCRM');
      const { toast } = await import('sonner');
      const { result } = renderHook(() => useDeleteCustomer(), { wrapper });

      await act(async () => {
        result.current.mutate('c-1');
      });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(toast.success).toHaveBeenCalledWith('客户已删除');
    });
  });

  describe('useCustomerTimeline', () => {
    it('正常获取活动时间线', async () => {
      const activities = [{ id: 'a-1', activity_type: 'call', content: '电话跟进' }];
      mockFetch.mockResolvedValueOnce({ success: true, data: activities });
      const { useCustomerTimeline } = await import('@/hooks/useCRM');
      const { result } = renderHook(() => useCustomerTimeline('c-1'), { wrapper });
      await waitFor(() => expect(result.current.data).toBeDefined());
      expect(result.current.data).toHaveLength(1);
    });
  });

  describe('useCustomerContacts', () => {
    it('正常获取联系人列表', async () => {
      const contacts = [{ id: 'ct-1', name: '张三', is_primary: true }];
      mockFetch.mockResolvedValueOnce({ success: true, data: contacts });
      const { useCustomerContacts } = await import('@/hooks/useCRM');
      const { result } = renderHook(() => useCustomerContacts('c-1'), { wrapper });
      await waitFor(() => expect(result.current.data).toBeDefined());
      expect(result.current.data).toHaveLength(1);
    });

    it('customerId 为 null 时不请求', async () => {
      const { useCustomerContacts } = await import('@/hooks/useCRM');
      renderHook(() => useCustomerContacts(null), { wrapper });
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('useCustomerStats', () => {
    it('正常获取统计数据', async () => {
      const stats = { total: 100, by_stage: { prospect: 30 } };
      mockFetch.mockResolvedValueOnce({ success: true, data: { stats } });
      const { useCustomerStats } = await import('@/hooks/useCRM');
      const { result } = renderHook(() => useCustomerStats(), { wrapper });
      await waitFor(() => expect(result.current.data).toBeDefined());
      expect(result.current.data?.total).toBe(100);
    });
  });

  describe('useCreateContact', () => {
    it('成功添加联系人', async () => {
      mockFetch.mockResolvedValueOnce({
        success: true, data: { contact: { id: 'ct-1', name: '李四' } },
      });
      const { useCreateContact } = await import('@/hooks/useCRM');
      const { toast } = await import('sonner');
      const { result } = renderHook(() => useCreateContact('c-1'), { wrapper });

      await act(async () => {
        result.current.mutate({ name: '李四', phone: '13800138000' } as any);
      });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(toast.success).toHaveBeenCalledWith('联系人已添加');
    });
  });

  describe('useCreateActivity', () => {
    it('成功添加跟进记录', async () => {
      mockFetch.mockResolvedValueOnce({
        success: true, data: { activity: { id: 'a-1' } },
      });
      const { useCreateActivity } = await import('@/hooks/useCRM');
      const { toast } = await import('sonner');
      const { result } = renderHook(() => useCreateActivity('c-1'), { wrapper });

      await act(async () => {
        result.current.mutate({ activity_type: 'call', content: '电话沟通' });
      });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(toast.success).toHaveBeenCalledWith('跟进记录已添加');
    });
  });
});
