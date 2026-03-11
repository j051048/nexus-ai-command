import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';

// 可变的 mock 用户数据，各测试可修改
let mockUserData = {
  id: 'user-001',
  name: '测试用户',
  role: 'employee' as string,
  department: '销售部',
  score: 50,
  rank: 1,
  totalBonus: 0,
  badges: [],
  avatar: '',
  employeeNumber: null,
  jobTitle: null,
};

vi.mock('@/contexts/UserContext', () => ({
  useUser: () => ({ user: mockUserData }),
}));

// Mock supabase
vi.mock('@/integrations/supabase/client', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: 'test-token' } },
      }),
    },
  },
}));

describe('usePermission', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 重置为默认用户
    mockUserData = {
      id: 'user-001',
      name: '测试用户',
      role: 'employee',
      department: '销售部',
      score: 50,
      rank: 1,
      totalBonus: 0,
      badges: [],
      avatar: '',
      employeeNumber: null,
      jobTitle: null,
    };
  });

  it('invalidatePermissionCache 应清除缓存且不抛异常', async () => {
    const { invalidatePermissionCache } = await import('@/hooks/usePermission');
    expect(() => invalidatePermissionCache()).not.toThrow();
  });

  it('usePermissions 中 employee 角色 read 应被允许', async () => {
    mockUserData.role = 'employee';
    const { usePermissions } = await import('@/hooks/usePermission');

    const { result } = renderHook(() =>
      usePermissions([
        { resource: 'chat', action: 'read' },
        { resource: 'documents', action: 'read' },
      ])
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(typeof result.current.can).toBe('function');
    expect(result.current.can('chat', 'read')).toBe(true);
    expect(result.current.can('documents', 'read')).toBe(true);
  });

  it('usePermissions 中 employee 角色 write chat/documents 应被允许', async () => {
    mockUserData.role = 'employee';
    const { usePermissions } = await import('@/hooks/usePermission');

    const { result } = renderHook(() =>
      usePermissions([
        { resource: 'chat', action: 'write' },
        { resource: 'documents', action: 'write' },
      ])
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.can('chat', 'write')).toBe(true);
    expect(result.current.can('documents', 'write')).toBe(true);
  });

  it('usePermissions 中 boss 角色应全部允许', async () => {
    mockUserData.role = 'boss';
    const { usePermissions } = await import('@/hooks/usePermission');

    const { result } = renderHook(() =>
      usePermissions([
        { resource: 'system', action: 'admin' },
        { resource: 'billing', action: 'delete' },
      ])
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.can('system', 'admin')).toBe(true);
    expect(result.current.can('billing', 'delete')).toBe(true);
  });

  it('usePermissions 中 employee 角色 delete 应被拒绝', async () => {
    mockUserData.role = 'employee';
    const { usePermissions } = await import('@/hooks/usePermission');

    const { result } = renderHook(() =>
      usePermissions([{ resource: 'projects', action: 'delete' }])
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.can('projects', 'delete')).toBe(false);
  });

  it('usePermissions 中 manager 角色 system 应被拒绝但 projects 允许', async () => {
    mockUserData.role = 'manager';
    const { usePermissions } = await import('@/hooks/usePermission');

    const { result } = renderHook(() =>
      usePermissions([
        { resource: 'system', action: 'write' },
        { resource: 'projects', action: 'write' },
      ])
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.can('system', 'write')).toBe(false);
    expect(result.current.can('projects', 'write')).toBe(true);
  });

  it('usePermissions 空 checks 应立即返回 loading=false', async () => {
    const { usePermissions } = await import('@/hooks/usePermission');

    const { result } = renderHook(() => usePermissions([]));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
  });
});
