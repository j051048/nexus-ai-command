import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  useCompetitors, useCompetitorDetail, useCompetitorProducts, useCreateCompetitor,
  useUpdateCompetitor, useDeleteCompetitor, useCreateProduct, useUpdateProduct,
  useDeleteProduct, useUpsertFeature, useDeleteFeature,
} from '@/hooks/useCompetitors';
import { useEntityRelations, usePatternInsights, useSearchEntities } from '@/hooks/useKnowledgeGraph';
import { useToolMetadata } from '@/hooks/useToolMetadata';
import { useTabCounts, useUnifiedApprovals } from '@/hooks/useUnifiedApprovals';
import { useApprovalTypeConfig } from '@/hooks/useApprovalTypeConfig';
import { useEnterpriseQueryScope } from '@/hooks/useEnterpriseQueryScope';

const mocks = vi.hoisted(() => ({
  auth: {
    user: { id: 'user-a' }, profile: { user_id: 'user-a', organization_id: 'org-a' },
    role: 'boss', isSuperAdmin: false, loading: false,
  },
  get: vi.fn(), fetch: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn(),
}));
vi.mock('@/components/auth/AuthContext', () => ({ useAuth: () => mocks.auth }));
vi.mock('@/api/aiClient', () => ({ aiClient: mocks }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const clients: QueryClient[] = [];
function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } });
  clients.push(client);
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function marker() { return `${mocks.auth.profile.organization_id}:${mocks.auth.user.id}:${mocks.auth.role}`; }
function payload(url: string) {
  const record = { id: marker(), name: marker(), related_tools: ['export'] };
  if (url.includes('/tools/metadata')) return { tools: [record, { name: 'export', related_tools: [] }], count: 2 };
  if (url.endsWith('/patterns')) return { entity_types: [], relation_types: [], top_entities: [record], total_entities: 1, total_relations: 0 };
  if (url.startsWith('api/approval/list')) return { items: [record], total: 1, page: 1, page_size: 20 };
  if (url.endsWith('/tab-counts')) return { pending: 1, mine: 0, marker: marker() };
  if (url === '/api/competitors/selected') return { competitor: record, products: [], features: [], documents: [] };
  return [record];
}

beforeEach(() => {
  mocks.auth.user.id = 'user-a';
  mocks.auth.profile = { user_id: 'user-a', organization_id: 'org-a' };
  mocks.auth.role = 'boss';
  mocks.auth.isSuperAdmin = false;
  mocks.auth.loading = false;
  mocks.get.mockReset().mockImplementation(async (url: string) => ({ data: { success: true, data: payload(url) } }));
  mocks.fetch.mockReset().mockImplementation(async (url: string) => ({ success: true, data: payload(url) }));
  for (const method of [mocks.post, mocks.put, mocks.delete]) method.mockReset().mockResolvedValue({ data: { success: true } });
});
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); });

const queries = [
  { name: 'competitors', useQuery: useCompetitors },
  { name: 'competitor detail', useQuery: () => useCompetitorDetail('selected') },
  { name: 'competitor products', useQuery: () => useCompetitorProducts('selected') },
  { name: 'knowledge search', useQuery: () => useSearchEntities('spectrometer') },
  { name: 'knowledge relations', useQuery: () => useEntityRelations('selected') },
  { name: 'knowledge patterns', useQuery: usePatternInsights },
  { name: 'approval list', useQuery: () => useUnifiedApprovals('pending') },
  { name: 'approval counts', useQuery: useTabCounts },
  { name: 'approval types', useQuery: useApprovalTypeConfig },
];

describe('enterprise query identity and payload contracts', () => {
  it.each(queries)('$name isolates tenant, user and role caches', async ({ useQuery }) => {
    const { result, rerender } = renderHook(useQuery, { wrapper: wrapper() });
    await waitFor(() => expect(JSON.stringify(result.current.data)).toContain(marker()));
    for (const change of [
      () => { mocks.auth.profile.organization_id = 'org-b'; },
      () => { mocks.auth.user.id = 'user-b'; mocks.auth.profile.user_id = 'user-b'; },
      () => { mocks.auth.role = 'employee'; },
    ]) {
      change();
      rerender();
      expect(result.current.data).toBeUndefined();
      await waitFor(() => expect(JSON.stringify(result.current.data)).toContain(marker()));
    }
    const calls = [...mocks.get.mock.calls, ...mocks.fetch.mock.calls];
    expect(calls.map(([, options]) => options.headers['X-Org-ID'])).toEqual(['org-a', 'org-b', 'org-b', 'org-b']);
    expect(calls.every(([, options]) => options.signal instanceof AbortSignal)).toBe(true);
  });

  it.each(queries)('$name does not fetch with an unresolved profile, even on manual refetch', async ({ useQuery }) => {
    mocks.auth.profile.user_id = 'another-user';
    const { result } = renderHook(useQuery, { wrapper: wrapper() });
    await act(async () => { await result.current.refetch(); });
    expect(result.current.data).toBeUndefined();
    expect(mocks.get).not.toHaveBeenCalled();
    expect(mocks.fetch).not.toHaveBeenCalled();
  });

  it.each(queries)('$name reports malformed responses instead of empty success', async ({ useQuery }) => {
    mocks.get.mockResolvedValue({ data: { success: true, data: null } });
    mocks.fetch.mockResolvedValue({ success: true, data: null });
    const { result } = renderHook(useQuery, { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });

  it('aborts a previous tenant request and ignores its late response', async () => {
    let finish!: (value: unknown) => void;
    mocks.get.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    const { result, rerender } = renderHook(useCompetitors, { wrapper: wrapper() });
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(1));
    const oldSignal = mocks.get.mock.calls[0][1].signal;
    mocks.auth.profile.organization_id = 'org-b';
    rerender();
    await waitFor(() => expect(JSON.stringify(result.current.data)).toContain('org-b'));
    expect(oldSignal.aborted).toBe(true);
    await act(async () => { finish({ data: { success: true, data: [{ id: 'org-a-private' }] } }); });
    expect(JSON.stringify(result.current.data)).toContain('org-b');
    expect(JSON.stringify(result.current.data)).not.toContain('org-a-private');
  });

  it('does not reuse a warm cache while the identity is being resolved', async () => {
    const { result, rerender } = renderHook(useCompetitors, { wrapper: wrapper() });
    await waitFor(() => expect(result.current.data).toBeDefined());
    mocks.auth.loading = true;
    rerender();
    expect(result.current.data).toBeUndefined();
    expect(mocks.get).toHaveBeenCalledTimes(1);
  });

  it('rejects building request options for an unresolved identity', () => {
    mocks.auth.profile.user_id = 'another-user';
    const { result } = renderHook(useEnterpriseQueryScope);
    expect(result.current.enabled).toBe(false);
    expect(() => result.current.options()).toThrow('企业身份');
  });

  it('loads related tools from the correct envelope and clears them on role downgrade', async () => {
    const { result, rerender } = renderHook(useToolMetadata, { wrapper: wrapper() });
    await waitFor(() => expect(result.current.tools).toHaveLength(2));
    expect(result.current.getRelatedTools(marker()).map(tool => tool.name)).toEqual(['export']);
    mocks.auth.role = 'employee';
    mocks.get.mockResolvedValue({ data: { success: true, data: { tools: [], count: 0 } } });
    rerender();
    expect(result.current.tools).toEqual([]);
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(2));
    expect(result.current.getRelatedTools('old-tool')).toEqual([]);
  });
});

describe('competitor mutation identity', () => {
  it('binds every write endpoint to the same organization as its query', async () => {
    const { result } = renderHook(() => ({
      create: useCreateCompetitor(), update: useUpdateCompetitor(), remove: useDeleteCompetitor(),
      addProduct: useCreateProduct(), updateProduct: useUpdateProduct(), removeProduct: useDeleteProduct(),
      feature: useUpsertFeature(), removeFeature: useDeleteFeature(),
    }), { wrapper: wrapper() });
    await act(async () => {
      await result.current.create.mutateAsync({ name: 'Spectrometer' });
      await result.current.update.mutateAsync({ id: 'c', data: {} });
      await result.current.remove.mutateAsync('c');
      await result.current.addProduct.mutateAsync({ competitorId: 'c', data: {} });
      await result.current.updateProduct.mutateAsync({ competitorId: 'c', productId: 'p', data: {} });
      await result.current.removeProduct.mutateAsync({ competitorId: 'c', productId: 'p' });
      await result.current.feature.mutateAsync({ competitorId: 'c', data: {} });
      await result.current.removeFeature.mutateAsync({ competitorId: 'c', featureId: 'f' });
    });
    const calls = [...mocks.post.mock.calls, ...mocks.put.mock.calls, ...mocks.delete.mock.calls];
    expect(calls).toHaveLength(8);
    for (const call of calls) expect(call.at(-1).headers).toEqual({ 'X-Org-ID': 'org-a' });
  });

  it('rejects a write before the profile belongs to the signed-in user', async () => {
    mocks.auth.profile.user_id = 'foreign-user';
    const { result } = renderHook(useCreateCompetitor, { wrapper: wrapper() });
    await act(async () => { await expect(result.current.mutateAsync({ name: 'Test' })).rejects.toThrow('企业身份'); });
    expect(mocks.post).not.toHaveBeenCalled();
  });
});
