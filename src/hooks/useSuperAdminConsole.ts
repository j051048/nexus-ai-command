import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { httpClient } from '@/lib/httpClient';

export interface PlatformStats {
  total_organizations: number;
  active_organizations: number;
  total_users: number;
  monthly_active_users: number;
  total_ai_calls_30d: number;
  paid_organizations: number;
  pending_access_requests: number;
}

export interface AdminSubscription {
  org_id: string;
  plan: string;
  status: string;
  current_period_end?: string | null;
  access_source?: string;
  approved_at?: string | null;
}

export interface AdminOrganization {
  id: string;
  name: string;
  slug: string;
  status: string;
  plan: string;
  created_at: string;
  access_state: string;
  subscription?: AdminSubscription | null;
  user_count?: number;
  ai_calls_30d?: number;
  quotas?: {
    monthly_token_limit?: number;
    monthly_api_call_limit?: number;
    storage_limit_mb?: number;
  } | null;
}

export interface SubscriptionRequest {
  id: string;
  org_id: string;
  requested_plan: string;
  requested_days: number;
  note?: string | null;
  status: string;
  created_at: string;
  organization?: { id: string; name: string; slug: string } | null;
}

export interface PendingBoss {
  user_id: string;
  name: string;
  email: string;
  created_at: string;
  organization_name: string;
}

export interface AuditLog {
  id: string;
  action: string;
  organization_id?: string;
  user_id?: string;
  details?: Record<string, unknown>;
  created_at: string;
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export function usePlatformStats() {
  return useQuery({
    queryKey: ['super-admin', 'stats'],
    queryFn: async () => (await httpClient.get<ApiResponse<PlatformStats>>('/api/admin/stats')).data.data,
    refetchInterval: 60_000,
  });
}

export function useAdminOrganizations(search = '') {
  return useQuery({
    queryKey: ['super-admin', 'organizations', search],
    queryFn: async () => {
      const response = await httpClient.get<ApiResponse<AdminOrganization[]>>('/api/admin/organizations', {
        params: { limit: 100, search: search || undefined },
      });
      return response.data.data;
    },
  });
}

export function useAdminOrganization(orgId?: string) {
  return useQuery({
    queryKey: ['super-admin', 'organization', orgId],
    queryFn: async () =>
      (await httpClient.get<ApiResponse<AdminOrganization>>(`/api/admin/organizations/${orgId}`)).data.data,
    enabled: Boolean(orgId),
  });
}

export function useSubscriptionRequests(status = 'pending') {
  return useQuery({
    queryKey: ['super-admin', 'subscription-requests', status],
    queryFn: async () => {
      const response = await httpClient.get<ApiResponse<{ requests: SubscriptionRequest[] }>>(
        '/api/admin/subscription-requests',
        { params: { status } },
      );
      return response.data.data.requests;
    },
  });
}

export function usePendingBosses() {
  return useQuery({
    queryKey: ['super-admin', 'pending-bosses'],
    queryFn: async () => {
      const response = await httpClient.get<ApiResponse<PendingBoss[]>>('/api/organization/admin/pending-bosses');
      return response.data.data ?? [];
    },
  });
}

export function useAdminAuditLogs() {
  return useQuery({
    queryKey: ['super-admin', 'audit-logs'],
    queryFn: async () =>
      (await httpClient.get<ApiResponse<AuditLog[]>>('/api/admin/audit-logs', { params: { limit: 100 } })).data.data,
  });
}

function useAdminMutation<TVariables>(mutationFn: (variables: TVariables) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['super-admin'] });
    },
  });
}

export function useDecideSubscriptionRequest() {
  return useAdminMutation(
    async ({ requestId, ...body }: { requestId: string; decision: string; reason: string; plan?: string; expires_at?: string }) =>
      httpClient.post(`/api/admin/subscription-requests/${requestId}/decision`, body),
  );
}

export function useSetOrganizationAccess() {
  return useAdminMutation(
    async ({ orgId, ...body }: { orgId: string; plan: string; expires_at?: string | null; reason: string }) =>
      httpClient.put(`/api/admin/organizations/${orgId}/access`, body),
  );
}

export function useUpdateOrganizationQuotas() {
  return useAdminMutation(
    async ({ orgId, ...body }: { orgId: string; reason: string; monthly_token_limit?: number; monthly_api_call_limit?: number; storage_limit_mb?: number }) =>
      httpClient.post(`/api/admin/organizations/${orgId}/update-quotas`, body),
  );
}

export function useOrganizationStatusAction() {
  return useAdminMutation(
    async ({ orgId, action, reason }: { orgId: string; action: 'suspend' | 'unsuspend'; reason?: string }) =>
      httpClient.post(`/api/admin/organizations/${orgId}/${action}`, action === 'suspend' ? { reason } : undefined),
  );
}

export function useDeleteOrganization() {
  return useAdminMutation(async ({ orgId }: { orgId: string }) =>
    httpClient.delete(`/api/organization/admin/organization/${orgId}`),
  );
}

export function useBossDecision() {
  return useAdminMutation(
    async ({ userId, decision }: { userId: string; decision: 'approve' | 'reject' }) =>
      httpClient.post(`/api/organization/admin/${decision}-boss/${userId}`),
  );
}
