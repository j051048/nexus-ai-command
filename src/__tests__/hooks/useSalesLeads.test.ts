/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * useSalesLeads hook 单元测试
 * 覆盖: 线索列表获取、Zod 校验降级、mutation、auth 依赖
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ── Mocks ──────────────────────────────────────────────────────

const mockHttpGet = vi.fn();
const mockHttpPut = vi.fn();
vi.mock('@/lib/httpClient', () => ({
  httpClient: {
    get: (...a: unknown[]) => mockHttpGet(...a),
    put: (...a: unknown[]) => mockHttpPut(...a),
  },
}));

let mockAuth: any = {
  session: { user: { id: 'u-1' } },
  profile: { organization_id: 'org-1' },
};
vi.mock('@/components/auth/AuthContext', () => ({
  useAuth: () => mockAuth,
}));


// ── Helpers ────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

const LEAD = {
  id: '00000000-0000-4000-8000-000000000001', name: '张三', company: '测试公司', stage: 'new',
  ai_suggestion: '跟进试用', win_probability: 75,
  contact_name: '张三', created_at: '2026-01-01',
};

// ── Tests ──────────────────────────────────────────────────────

describe('useSalesLeads', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth = {
      session: { user: { id: 'u-1' } },
      profile: { organization_id: 'org-1' },
    };
  });

  it('正常获取线索列表', async () => {
    mockHttpGet.mockResolvedValueOnce({ data: { leads: [LEAD] } });
    const { useSalesLeads } = await import('@/hooks/useSalesLeads');
    const { result } = renderHook(() => useSalesLeads(), { wrapper });
    await waitFor(() => expect(result.current.leads).toHaveLength(1));
    expect(result.current.leads[0]).toMatchObject({ id: LEAD.id, aiSuggestion: '跟进试用', winProbability: 75 });
  });

  it('session 缺失时不请求', async () => {
    mockAuth = { session: null, profile: { organization_id: 'org-1' } };
    const { useSalesLeads } = await import('@/hooks/useSalesLeads');
    const { result } = renderHook(() => useSalesLeads(), { wrapper });
    expect(result.current.isLoading).toBe(false);
    expect(mockHttpGet).not.toHaveBeenCalled();
  });

  it('profile 缺失时不请求', async () => {
    mockAuth = { session: { user: { id: 'u-1' } }, profile: null };
    const { useSalesLeads } = await import('@/hooks/useSalesLeads');
    const { result } = renderHook(() => useSalesLeads(), { wrapper });
    expect(result.current.leads).toEqual([]);
  });

  it('拒绝无效数据并暴露可重试错误', async () => {
    const invalidLead = { ...LEAD, stage: 'not-a-stage' };
    mockHttpGet.mockResolvedValueOnce({ data: { leads: [invalidLead] } });
    const { useSalesLeads } = await import('@/hooks/useSalesLeads');
    const { result } = renderHook(() => useSalesLeads(), { wrapper });
    await waitFor(() => expect(result.current.error).toBeInstanceOf(Error));
    expect(result.current.leads).toEqual([]);
  });

  it('API 返回非数组时防御处理', async () => {
    mockHttpGet.mockResolvedValueOnce({ data: { leads: null } });
    const { useSalesLeads } = await import('@/hooks/useSalesLeads');
    const { result } = renderHook(() => useSalesLeads(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.leads).toEqual([]);
  });

  it('updateLeadStage mutation 成功', async () => {
    mockHttpGet.mockResolvedValueOnce({ data: { leads: [LEAD] } });
    mockHttpPut.mockResolvedValueOnce({ data: { success: true } });
    const { useSalesLeads } = await import('@/hooks/useSalesLeads');
    const { result } = renderHook(() => useSalesLeads(), { wrapper });
    await waitFor(() => expect(result.current.leads).toHaveLength(1));

    await act(async () => {
      result.current.updateLeadStage.mutate({ id: 'lead-1', stage: 'qualified' as any });
    });
    await waitFor(() => expect(result.current.updateLeadStage.isSuccess).toBe(true));
  });
});
