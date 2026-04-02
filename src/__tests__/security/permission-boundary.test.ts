/**
 * 前端权限边界测试
 *
 * 覆盖：usePermission hook 的角色矩阵、缓存、降级
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockHttpGet = vi.fn();
vi.mock('@/lib/httpClient', () => ({
  httpClient: { get: (...a: unknown[]) => mockHttpGet(...a) },
}));

const mockAuth: any = {
  user: { id: 'u-1' },
  profile: { organization_id: 'org-1' },
  role: 'employee',
};
vi.mock('@/components/auth/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

describe('权限边界测试', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth.role = 'employee';
  });

  it('employee 无审批权限', async () => {
    mockHttpGet.mockResolvedValueOnce({
      data: { data: { allowed: false } },
    });

    const { usePermission } = await import('@/hooks/usePermission');
    const { result } = renderHook(
      () => usePermission('approval', 'approve'),
      { wrapper }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasPermission).toBe(false);
  });

  it('boss 有审批权限', async () => {
    mockAuth.role = 'boss';
    mockHttpGet.mockResolvedValueOnce({
      data: { data: { allowed: true } },
    });

    const { usePermission } = await import('@/hooks/usePermission');
    const { result } = renderHook(
      () => usePermission('approval', 'approve'),
      { wrapper }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasPermission).toBe(true);
  });

  it('API 错误时降级为无权限', async () => {
    mockHttpGet.mockRejectedValueOnce(new Error('Network error'));

    const { usePermission } = await import('@/hooks/usePermission');
    const { result } = renderHook(
      () => usePermission('admin', 'delete'),
      { wrapper }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    // 错误时应安全降级为无权限
    expect(result.current.hasPermission).toBe(false);
  });

  it('未登录时无权限', async () => {
    const saved = mockAuth.user;
    mockAuth.user = null;

    const { usePermission } = await import('@/hooks/usePermission');
    const { result } = renderHook(
      () => usePermission('any', 'action'),
      { wrapper }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasPermission).toBe(false);
    mockAuth.user = saved;
  });
});
