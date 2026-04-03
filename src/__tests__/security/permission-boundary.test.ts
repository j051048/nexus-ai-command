/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * 前端权限边界测试
 *
 * 覆盖：usePermission hook 的角色矩阵、缓存、降级
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';

// Mock supabase
vi.mock('@/integrations/supabase/client', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: 'test-jwt' } },
      }),
    },
  },
}));

// Mock apiConfig
vi.mock('@/lib/apiConfig', () => ({
  getApiBaseUrl: () => 'https://api.test.com',
}));

const mockUser: any = {
  id: 'u-1',
  role: 'employee',
};
vi.mock('@/contexts/UserContext', () => ({
  useUser: () => ({ user: mockUser }),
}));

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

import { usePermission, invalidatePermissionCache } from '@/hooks/usePermission';

describe('权限边界测试', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser.id = 'u-1';
    mockUser.role = 'employee';
    mockFetch.mockReset();
    invalidatePermissionCache();
  });

  it('employee 无审批权限（后端返回 allowed:false）', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ allowed: false }),
    });

    const { result } = renderHook(() => usePermission('approval', 'approve'));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.allowed).toBe(false);
  });

  it('boss 有审批权限（后端返回 allowed:true）', async () => {
    mockUser.role = 'boss';
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ allowed: true }),
    });

    const { result } = renderHook(() => usePermission('approval', 'approve'));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.allowed).toBe(true);
  });

  it('API 错误时降级为 fallback 角色检查', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => usePermission('approval', 'approve'));

    await waitFor(() => expect(result.current.loading).toBe(false));
    // employee fallback: action=approve on resource=approval → false
    expect(result.current.allowed).toBe(false);
  });

  it('未登录时无权限', async () => {
    const saved = mockUser.id;
    mockUser.id = null;

    const { result } = renderHook(() => usePermission('any', 'action'));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.allowed).toBe(false);
    mockUser.id = saved;
  });
});
