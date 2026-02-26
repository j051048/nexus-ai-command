/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';

// ─── Mock supabase ──────────────────────────────────────────

const mockGetSession = vi.fn();
const mockOnAuthStateChange = vi.fn();
const mockRpc = vi.fn();
const mockFrom = vi.fn();

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
      from: (...args: any[]) => mockFrom(...args),
      rpc: (...args: any[]) => mockRpc(...args),
    },
  };
});

// ─── Mock sonner toast ──────────────────────────────────────

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
  },
}));

// ─── 测试辅助 ──────────────────────────────────────────────

function createWrapper() {
  // Dynamic import to ensure mock is applied
  const { AuthProvider } = require('@/components/auth/AuthContext');
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(AuthProvider, null, children);
}

function setupDefaultMocks() {
  mockOnAuthStateChange.mockReturnValue({
    data: { subscription: { unsubscribe: vi.fn() } },
  });
  mockFrom.mockReturnValue({
    select: vi.fn().mockReturnThis(),
    eq: vi.fn().mockReturnThis(),
    maybeSingle: vi.fn().mockResolvedValue({ data: null, error: null }),
  });
  mockRpc.mockResolvedValue({ data: null });
}

// ─── 测试用例 ──────────────────────────────────────────────

describe('useAuth (AuthContext)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupDefaultMocks();
  });

  it('初始状态 loading=true', async () => {
    // No session — auth resolves immediately to no-user
    mockGetSession.mockResolvedValue({ data: { session: null } });

    const { AuthProvider, useAuth } = await import('@/components/auth/AuthContext');
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(AuthProvider, null, children);

    const { result } = renderHook(() => useAuth(), { wrapper });

    // Initially loading should be true (before getSession resolves)
    expect(result.current.loading).toBe(true);
  });

  it('无 session 时角色解析为 null，loading=false', async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });

    const { AuthProvider, useAuth } = await import('@/components/auth/AuthContext');
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(AuthProvider, null, children);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.user).toBeNull();
    expect(result.current.session).toBeNull();
    expect(result.current.role).toBeNull();
  });

  it('通过 get_user_role RPC 解析角色', async () => {
    const mockUser = { id: 'user-123', email: 'test@test.com' };
    const mockSession = { user: mockUser, access_token: 'token-abc' };

    mockGetSession.mockResolvedValue({ data: { session: mockSession } });
    mockRpc.mockResolvedValue({ data: 'manager' });
    mockFrom.mockReturnValue({
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      maybeSingle: vi.fn().mockResolvedValue({
        data: { id: 'user-123', full_name: 'Test User', role: 'employee' },
        error: null,
      }),
    });

    const { AuthProvider, useAuth } = await import('@/components/auth/AuthContext');
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(AuthProvider, null, children);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));

    // RPC returned 'manager', so role should be 'manager'
    expect(result.current.role).toBe('manager');
    expect(result.current.user).toEqual(mockUser);
  });

  it('RPC 返回 null 且 profile 无角色时，回退到 employee', async () => {
    const mockUser = { id: 'user-456', email: 'emp@test.com' };
    const mockSession = { user: mockUser, access_token: 'token-xyz' };

    mockGetSession.mockResolvedValue({ data: { session: mockSession } });
    mockRpc.mockResolvedValue({ data: null });
    mockFrom.mockReturnValue({
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      maybeSingle: vi.fn().mockResolvedValue({
        data: { id: 'user-456', full_name: 'Employee User' },
        error: null,
      }),
    });

    const { AuthProvider, useAuth } = await import('@/components/auth/AuthContext');
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(AuthProvider, null, children);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));

    // RPC returned null, profile has no role field → default to employee
    expect(result.current.role).toBe('employee');
  });

  it('RPC 返回 null 时，从 profile.role=founder 解析为 boss', async () => {
    const mockUser = { id: 'user-789', email: 'boss@test.com' };
    const mockSession = { user: mockUser, access_token: 'token-boss' };

    mockGetSession.mockResolvedValue({ data: { session: mockSession } });
    mockRpc.mockResolvedValue({ data: null });
    mockFrom.mockReturnValue({
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      maybeSingle: vi.fn().mockResolvedValue({
        data: { id: 'user-789', full_name: 'Boss User', role: 'founder' },
        error: null,
      }),
    });

    const { AuthProvider, useAuth } = await import('@/components/auth/AuthContext');
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(AuthProvider, null, children);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));

    // RPC returned null, profile.role='founder' → resolvedRole should be 'boss'
    expect(result.current.role).toBe('boss');
  });
});
