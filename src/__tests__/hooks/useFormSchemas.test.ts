import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ─── Mock aiClient ──────────────────────────────────────────

const mockFetch = vi.fn();

vi.mock('@/api/aiClient', () => ({
  aiClient: {
    fetch: (...args: any[]) => mockFetch(...args),
  },
}));

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

// ─── 测试辅助 ──────────────────────────────────────────────

const mockSchemas = [
  {
    id: 'schema-1',
    name: '请假表单',
    approval_type: 'leave',
    fields: [
      { key: 'reason', label: '请假原因', type: 'text', required: true },
      { key: 'days', label: '天数', type: 'number', required: true },
    ],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 'schema-2',
    name: '报销表单',
    approval_type: 'expense',
    fields: [
      { key: 'amount', label: '金额', type: 'number', required: true },
    ],
  },
];

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

describe('useFormSchemas', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('成功获取表单 schema 列表', async () => {
    mockFetch.mockResolvedValueOnce(mockSchemas);

    const { useFormSchemas } = await import('@/hooks/useFormSchemas');
    const { result } = renderHook(() => useFormSchemas(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(2);
    expect(result.current.data![0].name).toBe('请假表单');
    expect(mockFetch).toHaveBeenCalledWith('api/form-schemas');
  });

  it('API 调用失败时返回错误', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network Error'));

    const { useFormSchemas } = await import('@/hooks/useFormSchemas');
    const { result } = renderHook(() => useFormSchemas(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe('Network Error');
  });

  it('useFormSchema 使用正确 ID 请求', async () => {
    mockFetch.mockResolvedValueOnce(mockSchemas[0]);

    const { useFormSchema } = await import('@/hooks/useFormSchemas');
    const { result } = renderHook(() => useFormSchema('schema-1'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.name).toBe('请假表单');
    expect(mockFetch).toHaveBeenCalledWith('api/form-schemas/schema-1');
  });

  it('useFormSchemaByType 使用审批类型请求', async () => {
    mockFetch.mockResolvedValueOnce(mockSchemas[1]);

    const { useFormSchemaByType } = await import('@/hooks/useFormSchemas');
    const { result } = renderHook(() => useFormSchemaByType('expense'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.approval_type).toBe('expense');
    expect(mockFetch).toHaveBeenCalledWith('api/form-schemas/by-type/expense');
  });
});
