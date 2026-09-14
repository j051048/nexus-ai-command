import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
import { type ApiPayload, unwrapApiData, unwrapApiList } from '@/api/response';
import { useEnterpriseQueryScope } from '@/hooks/useEnterpriseQueryScope';
import { toast } from 'sonner';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyData = Record<string, any>;

export interface Competitor {
  id: string;
  organization_id: string;
  name: string;
  brand_names: string[];
  industry: string;
  tag: string;
  logo_url: string | null;
  website: string | null;
  description: string;
  strength_summary: string;
  weakness_summary: string;
  threat_level: 'low' | 'medium' | 'high' | 'critical';
  is_active: boolean;
  sort_order: number;
  metadata: AnyData;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface CompetitorProduct {
  id: string;
  competitor_id: string;
  name: string;
  model: string;
  category: string;
  price_range: string;
  description: string;
  specs: AnyData;
  our_competing_product: string;
  comparison_notes: string;
  created_at: string;
}

export interface CompetitorFeature {
  id: string;
  competitor_id: string;
  dimension: string;
  competitor_score: number | null;
  our_score: number | null;
  competitor_detail: string;
  our_advantage: string;
  counter_strategy: string;
  created_at: string;
}

export interface CompetitorDocument {
  competitor_id: string;
  document_id: string;
  doc_type: string;
  document?: {
    id: string;
    title: string;
    file_type: string;
    file_size: number;
    created_at: string;
  };
}

export interface CompetitorDetail {
  competitor: Competitor;
  products: CompetitorProduct[];
  features: CompetitorFeature[];
  documents: CompetitorDocument[];
}

// ─── List competitors ──────────────────────────────────

export function useCompetitors() {
  const scope = useEnterpriseQueryScope();
  return useQuery<Competitor[]>({
    queryKey: ['competitors', ...scope.key],
    enabled: scope.enabled,
    queryFn: async ({ signal }) => {
      const res = await aiClient.get<ApiPayload<Competitor[]>>('/api/competitors', scope.options(signal));
      return unwrapApiList(res.data);
    },
  });
}

// ─── Get competitor detail ─────────────────────────────

export function useCompetitorDetail(competitorId: string | null) {
  const scope = useEnterpriseQueryScope();
  return useQuery<CompetitorDetail>({
    queryKey: ['competitor-detail', competitorId, ...scope.key],
    queryFn: async ({ signal }) => {
      const res = await aiClient.get<ApiPayload<CompetitorDetail>>(`/api/competitors/${competitorId}`, scope.options(signal));
      const detail = unwrapApiData(res.data);
      if (!detail?.competitor?.id) throw new Error('竞品资料格式异常，请重试');
      return {
        competitor: detail.competitor,
        products: Array.isArray(detail?.products) ? detail.products : [],
        features: Array.isArray(detail?.features) ? detail.features : [],
        documents: Array.isArray(detail?.documents) ? detail.documents : [],
      };
    },
    enabled: scope.enabled && !!competitorId,
  });
}

// ─── Create competitor ─────────────────────────────────

export function useCreateCompetitor() {
  const scope = useEnterpriseQueryScope();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<Competitor>) => {
      const res = await aiClient.post('/api/competitors', data, scope.options());
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['competitors'] });
      toast.success('竞品创建成功');
    },
    onError: (err: Error) => {
      toast.error(err.message || '创建失败');
    },
  });
}

// ─── Update competitor ─────────────────────────────────

export function useUpdateCompetitor() {
  const scope = useEnterpriseQueryScope();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<Competitor> }) => {
      const res = await aiClient.put(`/api/competitors/${id}`, data, scope.options());
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['competitors'] });
      qc.invalidateQueries({ queryKey: ['competitor-detail'] });
      toast.success('竞品更新成功');
    },
    onError: (err: Error) => {
      toast.error(err.message || '更新失败');
    },
  });
}

// ─── Delete competitor ─────────────────────────────────

export function useDeleteCompetitor() {
  const scope = useEnterpriseQueryScope();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await aiClient.delete(`/api/competitors/${id}`, scope.options());
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['competitors'] });
      toast.success('竞品已删除');
    },
    onError: (err: Error) => {
      toast.error(err.message || '删除失败');
    },
  });
}

// ─── Products CRUD ─────────────────────────────────────

export function useCompetitorProducts(competitorId: string | null) {
  const scope = useEnterpriseQueryScope();
  return useQuery<CompetitorProduct[]>({
    queryKey: ['competitor-products', competitorId, ...scope.key],
    queryFn: async ({ signal }) => {
      const res = await aiClient.get<ApiPayload<CompetitorProduct[]>>(`/api/competitors/${competitorId}/products`, scope.options(signal));
      return unwrapApiList(res.data);
    },
    enabled: scope.enabled && !!competitorId,
  });
}

export function useCreateProduct() {
  const scope = useEnterpriseQueryScope();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ competitorId, data }: { competitorId: string; data: Partial<CompetitorProduct> }) => {
      const res = await aiClient.post(`/api/competitors/${competitorId}/products`, data, scope.options());
      return res.data;
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ['competitor-products', vars.competitorId] });
      qc.invalidateQueries({ queryKey: ['competitor-detail', vars.competitorId] });
      toast.success('产品添加成功');
    },
    onError: (err: Error) => {
      toast.error(err.message || '添加失败');
    },
  });
}

export function useUpdateProduct() {
  const scope = useEnterpriseQueryScope();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ competitorId, productId, data }: { competitorId: string; productId: string; data: Partial<CompetitorProduct> }) => {
      const res = await aiClient.put(`/api/competitors/${competitorId}/products/${productId}`, data, scope.options());
      return res.data;
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ['competitor-products', vars.competitorId] });
      qc.invalidateQueries({ queryKey: ['competitor-detail', vars.competitorId] });
      toast.success('产品更新成功');
    },
    onError: (err: Error) => {
      toast.error(err.message || '更新失败');
    },
  });
}

export function useDeleteProduct() {
  const scope = useEnterpriseQueryScope();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ competitorId, productId }: { competitorId: string; productId: string }) => {
      await aiClient.delete(`/api/competitors/${competitorId}/products/${productId}`, scope.options());
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ['competitor-products', vars.competitorId] });
      qc.invalidateQueries({ queryKey: ['competitor-detail', vars.competitorId] });
      toast.success('产品已删除');
    },
    onError: (err: Error) => {
      toast.error(err.message || '删除失败');
    },
  });
}

// ─── Features CRUD ─────────────────────────────────────

export function useUpsertFeature() {
  const scope = useEnterpriseQueryScope();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ competitorId, data }: { competitorId: string; data: Partial<CompetitorFeature> }) => {
      const res = await aiClient.post(`/api/competitors/${competitorId}/features`, data, scope.options());
      return res.data;
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ['competitor-detail', vars.competitorId] });
      toast.success('对比维度保存成功');
    },
    onError: (err: Error) => {
      toast.error(err.message || '保存失败');
    },
  });
}

export function useDeleteFeature() {
  const scope = useEnterpriseQueryScope();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ competitorId, featureId }: { competitorId: string; featureId: string }) => {
      await aiClient.delete(`/api/competitors/${competitorId}/features/${featureId}`, scope.options());
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ['competitor-detail', vars.competitorId] });
      toast.success('对比维度已删除');
    },
    onError: (err: Error) => {
      toast.error(err.message || '删除失败');
    },
  });
}
