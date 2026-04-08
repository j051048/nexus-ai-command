/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';

// ─── Mock supabase ──────────────────────────────────────────

const mockGetSession = vi.fn();
const mockOnAuthStateChange = vi.fn();
const mockRpc = vi.fn();
const mockSelect = vi.fn();
const mockEq = vi.fn();
const mockMaybeSingle = vi.fn();

vi.mock('@/integrations/supabase/client', () => {
  return {
    supabase: {
      auth: {
        getSession: (...args: any[]) => mockGetSession(...args),
        onAuthStateChange: (...args: any[]) => mockOnAuthStateChange(...args),
        signInWithPassword: vi.fn(),
        signUp: vi.fn(),
        signOut: vi.fn(),
      },
      from: () => ({
        select: mockSelect,
      }),
      rpc: (...args: any[]) => mockRpc(...args),
    },
  };
});

// Mock httpClient
vi.mock('@/lib/httpClient', () => ({
  httpClient: {
    get: vi.fn().mockResolvedValue({ data: { data: { user: null } } }),
    post: vi.fn(),
  },
}));

// ─── Mock sonner toast ──────────────────────────────────────

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
  },
}));

// ─── 测试辅助 ──────────────────────────────────────────────

function setupDefaultMocks() {
  // Mock auth state change listener
  mockOnAuthStateChange.mockImplementation((callback) => {
    // Immediately trigger callback with SIGNED_IN event if session exists
    setTimeout(() => {
      const session = mockGetSession.mock.results[0]?.value?.data?.session;
      if (session) {
        callback('SIGNED_IN', { session });
      }
    }, 0);
    return { data: { subscription: { unsubscribe: vi.fn() } } };
  });

  // Mock database queries
  mockSelect.mockReturnValue({ eq: mockEq });
  mockEq.mockReturnValue({ maybeSingle: mockMaybeSingle });
  mockMaybeSingle.mockResolvedValue({ data: null, error: null });
  
  // Default mock for RPC handles both role and admin checks
  mockRpc.mockImplementation((name) => {
    if (name === 'get_user_role') return Promise.resolve({ data: 'employee', error: null });
    if (name === 'is_super_admin') return Promise.resolve({ data: false, error: null });
    return Promise.resolve({ data: null, error: null });
  });
}

// ─── 测试用例 ──────────────────────────────────────────────

describe('useAuth (AuthContext)', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    setupDefaultMocks();
  });

  it('初始状态 loading=true', async () => {
    mockGetSession.mockResolvedValue({ data: { session: null }, error: null });

    const { AuthProvider, useAuth } = await import('@/components/auth/AuthContext');
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(AuthProvider, null, children);

    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.loading).toBe(true);
    
    // 等待状态 settling 完成，避免产生 act 警告
    await waitFor(() => expect(result.current.loading).toBe(false), { timeout: 3000 });
  });

  it('无 session 时角色解析为 null，loading=false', async () => {
    mockGetSession.mockResolvedValue({ data: { session: null }, error: null });

    const { AuthProvider, useAuth } = await import('@/components/auth/AuthContext');
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(AuthProvider, null, children);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false), { timeout: 3000 });

    expect(result.current.user).toBeNull();
    expect(result.current.session).toBeNull();
    expect(result.current.role).toBeNull();
  });

  it('通过 get_user_role RPC 解析角色', async () => {
    const mockUser = { id: 'user-123', email: 'test@test.com' };
    const mockSession = { user: mockUser, access_token: 'mock-token-123' };

    mockGetSession.mockResolvedValue({ data: { session: mockSession }, error: null });
    
    // Inject custom RPC for this test
    mockRpc.mockImplementation((name) => {
      if (name === 'get_user_role') return Promise.resolve({ data: 'manager', error: null });
      return Promise.resolve({ data: false, error: null });
    });

    const { AuthProvider, useAuth } = await import('@/components/auth/AuthContext');
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(AuthProvider, null, children);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false), { timeout: 3000 });

    expect(result.current.role).toBe('manager');
    expect(result.current.user).toEqual(mockUser);
  });

  it('RPC 返回 null 且 profile 无角色时，回退到 employee', async () => {
    const mockUser = { id: 'user-456', email: 'emp@test.com' };
    const mockSession = { user: mockUser, access_token: 'token-xyz' };

    mockGetSession.mockResolvedValue({ data: { session: mockSession }, error: null });
    mockRpc.mockResolvedValue({ data: null, error: null });
    
    // AuthContext also uses httpClient.get('/api/users/profile')
    const { httpClient } = await import('@/lib/httpClient');
    (httpClient.get as any).mockResolvedValue({
      data: { data: { user: { id: 'user-456', name: 'Employee User' } } }
    });

    const { AuthProvider, useAuth } = await import('@/components/auth/AuthContext');
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(AuthProvider, null, children);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.role).toBe('employee'), { timeout: 3000 });
    expect(result.current.loading).toBe(false);
  });

  it('RPC 返回 null 时，从 profile.role=founder 解析为 boss', async () => {
    const mockUser = { id: 'user-789', email: 'boss@test.com' };
    const mockSession = { user: mockUser, access_token: 'token-boss' };

    mockGetSession.mockResolvedValue({ data: { session: mockSession }, error: null });
    mockRpc.mockResolvedValue({ data: null, error: null });
    
    // Mock profile role
    const { httpClient } = await import('@/lib/httpClient');
    (httpClient.get as any).mockResolvedValue({
      data: { data: { user: { id: 'user-789', name: 'Boss User', role: 'founder' } } }
    });

    const { AuthProvider, useAuth } = await import('@/components/auth/AuthContext');
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(AuthProvider, null, children);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.role).toBe('boss'), { timeout: 3000 });
  });
});
