import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
import { toast } from 'sonner';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyData = Record<string, any>;

export interface Customer {
  id: string;
  organization_id: string;
  name: string;
  company: string;
  industry: string;
  stage: string;
  source: string;
  estimated_value: number;
  assigned_to: string | null;
  tags: string[];
  metadata: AnyData;
  created_at: string;
  updated_at: string;
}

export interface CustomerContact {
  id: string;
  customer_id: string;
  name: string;
  title: string;
  phone: string;
  email: string;
  is_primary: boolean;
  created_at: string;
}

export interface CustomerActivity {
  id: string;
  customer_id: string;
  user_id: string;
  activity_type: string;
  content: string;
  created_at: string;
}

interface Filters {
  stage?: string;
  industry?: string;
  search?: string;
}

export function useCustomers(filters: Filters = {}) {
  return useInfiniteQuery({
    queryKey: ['crm-customers', filters],
    queryFn: async ({ pageParam = 0 }) => {
      const params = new URLSearchParams();
      if (filters.stage) params.set('stage', filters.stage);
      if (filters.industry) params.set('industry', filters.industry);
      if (filters.search) params.set('search', filters.search);
      params.set('offset', String(pageParam * 50));
      params.set('limit', '50');

      const res = await aiClient.fetch<{
        success: boolean;
        data: Customer[];
        total: number;
      }>(`api/crm/customers?${params.toString()}`);

      return {
        data: res.data,
        total: res.total,
        hasMore: res.data.length === 50 && (pageParam + 1) * 50 < res.total
      };
    },
    getNextPageParam: (lastPage, pages) => {
      return lastPage.hasMore ? pages.length : undefined;
    },
    initialPageParam: 0,
    staleTime: 30_000,
  });
}

export function useCustomer(id: string | null) {
  return useQuery({
    queryKey: ['crm-customer', id],
    queryFn: async () => {
      if (!id) return null;
      const res = await aiClient.fetch<{ success: boolean; data: { customer: Customer } }>(
        `api/crm/customers/${id}`
      );
      return res.data.customer;
    },
    enabled: !!id,
  });
}

export function useCreateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<Customer>) => {
      const res = await aiClient.fetch<{ success: boolean; data: { customer: Customer } }>(
        'api/crm/customers',
        { method: 'POST', body: JSON.stringify(data) }
      );
      return res.data.customer;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-customers'] });
      queryClient.invalidateQueries({ queryKey: ['crm-stats'] });
      toast.success('客户创建成功');
    },
    onError: (err: Error) => {
      toast.error(err.message || '创建客户失败');
    },
  });
}

export function useUpdateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<Customer> }) => {
      const res = await aiClient.fetch<{ success: boolean; data: { customer: Customer } }>(
        `api/crm/customers/${id}`,
        { method: 'PUT', body: JSON.stringify(data) }
      );
      return res.data.customer;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['crm-customers'] });
      queryClient.invalidateQueries({ queryKey: ['crm-customer', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['crm-stats'] });
      toast.success('客户信息已更新');
    },
    onError: (err: Error) => {
      toast.error(err.message || '更新客户失败');
    },
  });
}

export function useCustomerTimeline(customerId: string | null) {
  return useQuery({
    queryKey: ['crm-timeline', customerId],
    queryFn: async () => {
      if (!customerId) return [];
      const res = await aiClient.fetch<{ success: boolean; data: CustomerActivity[] }>(
        `api/crm/customers/${customerId}/timeline`
      );
      return res.data;
    },
    enabled: !!customerId,
  });
}

export function useCustomerContacts(customerId: string | null) {
  return useQuery({
    queryKey: ['crm-contacts', customerId],
    queryFn: async () => {
      if (!customerId) return [];
      const res = await aiClient.fetch<{ success: boolean; data: CustomerContact[] }>(
        `api/crm/customers/${customerId}/contacts`
      );
      return res.data;
    },
    enabled: !!customerId,
  });
}

export function useCustomerStats() {
  return useQuery({
    queryKey: ['crm-stats'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { stats: AnyData } }>(
        'api/crm/stats'
      );
      return res.data.stats;
    },
    staleTime: 60_000,
  });
}

export function useDeleteCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await aiClient.fetch(`api/crm/customers/${id}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-customers'] });
      queryClient.invalidateQueries({ queryKey: ['crm-stats'] });
      toast.success('客户已删除');
    },
    onError: (err: Error) => {
      toast.error(err.message || '删除客户失败');
    },
  });
}

export function useCreateContact(customerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<CustomerContact>) => {
      const res = await aiClient.fetch<{ success: boolean; data: { contact: CustomerContact } }>(
        `api/crm/customers/${customerId}/contacts`,
        { method: 'POST', body: JSON.stringify(data) }
      );
      return res.data.contact;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-contacts', customerId] });
      toast.success('联系人已添加');
    },
    onError: (err: Error) => {
      toast.error(err.message || '添加联系人失败');
    },
  });
}

export function useUpdateContact(customerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ contactId, data }: { contactId: string; data: Partial<CustomerContact> }) => {
      const res = await aiClient.fetch<{ success: boolean; data: { contact: CustomerContact } }>(
        `api/crm/customers/${customerId}/contacts/${contactId}`,
        { method: 'PUT', body: JSON.stringify(data) }
      );
      return res.data.contact;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-contacts', customerId] });
      toast.success('联系人已更新');
    },
    onError: (err: Error) => {
      toast.error(err.message || '更新联系人失败');
    },
  });
}

export function useDeleteContact(customerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (contactId: string) => {
      await aiClient.fetch(
        `api/crm/customers/${customerId}/contacts/${contactId}`,
        { method: 'DELETE' }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-contacts', customerId] });
      toast.success('联系人已删除');
    },
    onError: (err: Error) => {
      toast.error(err.message || '删除联系人失败');
    },
  });
}

export function useCreateActivity(customerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { activity_type: string; content: string }) => {
      const res = await aiClient.fetch<{ success: boolean; data: { activity: CustomerActivity } }>(
        `api/crm/customers/${customerId}/activities`,
        { method: 'POST', body: JSON.stringify(data) }
      );
      return res.data.activity;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-timeline', customerId] });
      toast.success('跟进记录已添加');
    },
    onError: (err: Error) => {
      toast.error(err.message || '添加跟进记录失败');
    },
  });
}

// ---------------------------------------------------------------------------
// Customer Health Score & Churn Prediction
// ---------------------------------------------------------------------------

export interface CustomerHealth {
  customer_id: string;
  health_score: number;
  risk_level: 'healthy' | 'at_risk' | 'churn_risk' | 'unknown';
  breakdown: {
    activity_recency: number;
    activity_frequency: number;
    contact_richness: number;
    stage_progression: number;
    value_indicator: number;
  };
  days_since_last_activity: number | null;
  activities_last_30d: number;
  contact_count: number;
  stage: string;
  estimated_value: number;
}

export interface HealthOverview {
  customers: Array<{
    id: string;
    name: string;
    stage: string;
    estimated_value: number;
    quick_score: number;
    risk_level: string;
  }>;
  summary: {
    healthy: number;
    at_risk: number;
    churn_risk: number;
  };
}

export function useCustomerHealth(customerId: string | null) {
  return useQuery({
    queryKey: ['crm-health', customerId],
    queryFn: async () => {
      if (!customerId) return null;
      const res = await aiClient.fetch<{ success: boolean; data: CustomerHealth }>(
        `api/crm/customers/${customerId}/health`
      );
      return res.data;
    },
    enabled: !!customerId,
    staleTime: 60_000,
  });
}

export function useHealthOverview() {
  return useQuery({
    queryKey: ['crm-health-overview'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: HealthOverview }>(
        'api/crm/health-overview'
      );
      return res.data;
    },
    staleTime: 60_000,
  });
}
