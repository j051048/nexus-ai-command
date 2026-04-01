import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthContext';
import { aiClient } from '@/api/aiClient';
import { toast } from 'sonner';
import { httpClient } from '@/lib/httpClient';

export interface ContractEvent {
  id: string;
  contract_id: string;
  event_type: string;
  description: string;
  user_id?: string;
  created_at: string;
}

export interface Contract {
  id: string;
  organization_id: string;
  title: string;
  customer_id: string | null;
  customer_name?: string;
  contract_number: string;
  contract_type: string;
  status: string;
  amount: number | null;
  currency: string;
  start_date: string;
  end_date: string;
  signed_by: string | null;
  signed_at: string | null;
  document_url: string | null;
  tags: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ContractWithEvents extends Contract {
  events: ContractEvent[];
}

/** Fetch all contracts for the current organization */
export function useContracts(filters?: { status?: string; search?: string }) {
  const { profile } = useAuth();
  const orgId = profile?.organization_id;

  return useQuery({
    queryKey: ['contracts', orgId, filters?.status, filters?.search],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters?.status && filters.status !== 'all') params.append('status', filters.status);
      if (filters?.search) params.append('search', filters.search);

      const response = await httpClient.get(`/api/contracts?${params}`);
      return response.data?.contracts || [];
    },
    enabled: !!orgId,
  });
}

/** Fetch a single contract with its events */
export function useContractDetail(contractId: string | null) {
  return useQuery({
    queryKey: ['contract-detail', contractId],
    queryFn: async () => {
      if (!contractId) return null;
      const response = await httpClient.get(`/api/contracts/${contractId}/events`);
      return response.data?.events || [];
    },
    enabled: !!contractId,
  });
}

/** Create a new contract */
export function useCreateContract() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: {
      title: string;
      customer_name?: string;
      contract_number?: string;
      contract_type: string;
      amount?: number | null;
      start_date?: string;
      end_date?: string;
    }) => {
      const response = await httpClient.post('/api/contracts', input);
      return response.data?.contract;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
    },
  });
}

/** Update contract status or fields */
export function useUpdateContract() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: {
      id: string;
      updates: Partial<Pick<Contract, 'title' | 'status' | 'amount' | 'start_date' | 'end_date' | 'contract_type' | 'tags'>>;
      eventDescription?: string;
    }) => {
      const response = await httpClient.put(`/api/contracts/${input.id}`, input.updates);
      return response.data?.contract;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
      queryClient.invalidateQueries({ queryKey: ['contract-detail'] });
    },
  });
}

/** Delete a contract (soft delete via backend API, boss role required) */
export function useDeleteContract() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (contractId: string) => {
      await aiClient.fetch(`api/contracts/${contractId}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
      queryClient.invalidateQueries({ queryKey: ['contract-detail'] });
      toast.success('合同已删除');
    },
    onError: (err: Error) => toast.error(err.message || '删除合同失败'),
  });
}
