import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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
  return useQuery({
    queryKey: ['crm-customers', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.stage) params.set('stage', filters.stage);
      if (filters.industry) params.set('industry', filters.industry);
      if (filters.search) params.set('search', filters.search);
      const qs = params.toString();
      const res = await aiClient.fetch<{ success: boolean; data: Customer[] }>(
        `api/crm/customers${qs ? '?' + qs : ''}`
      );
      return res.data;
    },
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
