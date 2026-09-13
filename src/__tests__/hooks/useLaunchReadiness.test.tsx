import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useLaunchReadiness } from '@/hooks/useLaunchReadiness';
import { useActivationState } from '@/hooks/useActivationState';

const mocks = vi.hoisted(() => ({
  auth: { profile: { organization_id: 'org-a' }, user: { id: 'u' } },
  get: vi.fn(), patch: vi.fn(),
}));
vi.mock('@/components/auth/AuthContext', () => ({ useAuth: () => mocks.auth }));
vi.mock('@/lib/httpClient', () => ({ httpClient: { get: mocks.get, patch: mocks.patch } }));

function createWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

beforeEach(() => {
  mocks.auth.profile.organization_id = 'org-a';
  mocks.auth.user.id = 'u';
  mocks.get.mockReset();
  mocks.patch.mockReset().mockResolvedValue({ data: {} });
  const storage = new Map<string, string>();
  vi.mocked(localStorage.getItem).mockImplementation((key) => storage.get(key) ?? null);
  vi.mocked(localStorage.setItem).mockImplementation((key, value) => { storage.set(key, value); });
});
afterEach(cleanup);

describe('launch scope', () => {
  it('binds readiness requests and cache to the current tenant', async () => {
    mocks.get.mockImplementation(async () => ({ data: { data: {
      organization_id: mocks.auth.profile.organization_id, user_id: 'u', uploaded: true,
    } } }));
    const { result, rerender } = renderHook(useLaunchReadiness, { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.data?.organization_id).toBe('org-a'));
    expect(mocks.get.mock.calls[0][1].headers['X-Org-ID']).toBe('org-a');
    mocks.auth.profile.organization_id = 'org-b';
    rerender();
    expect(result.current.data).toBeUndefined();
    await waitFor(() => expect(result.current.data?.organization_id).toBe('org-b'));
  });

  it('rejects a response belonging to a different tenant', async () => {
    mocks.get.mockResolvedValue({ data: { data: { organization_id: 'foreign', user_id: 'u' } } });
    const { result } = renderHook(useLaunchReadiness, { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 4000 });
    expect(result.current.data).toBeUndefined();
  });

  it('ignores an old tenant response after switching organizations', async () => {
    let finishOld!: (value: unknown) => void;
    mocks.get.mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; }))
      .mockResolvedValue({ data: { data: { company_name: 'Company B' } } });
    const { result, rerender } = renderHook(useActivationState);
    mocks.auth.profile.organization_id = 'org-b';
    rerender();
    await waitFor(() => expect(result.current.state.companyName).toBe('Company B'));
    await act(async () => { finishOld({ data: { data: { company_name: 'Company A' } } }); });
    expect(result.current.scope).toBe('org-b:u');
    expect(result.current.state.companyName).toBe('Company B');
    expect(mocks.get.mock.calls[1][1].headers['X-Org-ID']).toBe('org-b');
  });
});
