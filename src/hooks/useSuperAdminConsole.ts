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
  priority?: 'low' | 'normal' | 'high' | 'urgent';
  due_at?: string | null;
  waiting_seconds?: number;
  is_overdue?: boolean;
}

export interface AdminContext {
  user_id: string;
  admin_role: string;
  permissions: string[];
  active: boolean;
}

export interface AccessChange {
  id: string;
  org_id: string;
  change_kind: string;
  change_status: 'scheduled' | 'applied' | 'cancelled' | 'rolled_back' | 'failed';
  previous_snapshot?: Record<string, unknown> | null;
  next_snapshot: { plan: string; status: string; current_period_end?: string | null };
  reason: string;
  effective_at: string;
  applied_at?: string | null;
  created_by: string;
  created_at: string;
}

export interface CommercialRecord {
  id: string;
  org_id: string;
  order_number: string;
  contract_number?: string | null;
  amount_cents: number;
  discount_cents: number;
  currency: string;
  payment_status: string;
  paid_at?: string | null;
  due_at?: string | null;
  invoice_status: string;
  invoice_number?: string | null;
  sales_owner?: string | null;
  gifted_days: number;
  evidence_url?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface OperationalException {
  id: string;
  org_id: string;
  organization_name: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  detail: string;
  occurred_at?: string | null;
  recommended_action: string;
}

export interface OperationalAnalytics {
  plan_distribution: Record<string, number>;
  expiring: { '7_days': number; '30_days': number; '90_days': number };
  requests_30d: Record<string, number>;
  average_review_hours: number;
  commercial: { collected_cents: number; outstanding_cents: number; overdue_orders: number };
  top_cost_organizations: Array<{
    org_id: string;
    organization_name: string;
    cost_usd: number;
    tokens: number;
    requests: number;
  }>;
}

export interface Organization360 extends AdminOrganization {
  active_users_30d: number;
  usage_30d: { requests: number; tokens: number; cost_usd: number };
  users: Array<{
    id: string;
    email?: string | null;
    full_name?: string | null;
    role: string;
    status: string;
    last_active_at?: string | null;
  }>;
  access_requests: SubscriptionRequest[];
  access_versions: AccessChange[];
  commercial_records: CommercialRecord[];
  audit_timeline: AuditLog[];
}

export interface PlatformAdminAssignment {
  user_id: string;
  admin_role: string;
  permissions: string[];
  active: boolean;
  user?: { full_name?: string | null; email?: string | null; status?: string } | null;
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

export function useAdminContext() {
  return useQuery({
    queryKey: ['super-admin', 'context'],
    queryFn: async () => (await httpClient.get<ApiResponse<AdminContext>>('/api/admin/me')).data.data,
    staleTime: 5 * 60_000,
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

export function useAdminOrganization360(orgId?: string) {
  return useQuery({
    queryKey: ['super-admin', 'organization-360', orgId],
    queryFn: async () =>
      (await httpClient.get<ApiResponse<Organization360>>(`/api/admin/organizations/${orgId}/overview`)).data.data,
    enabled: Boolean(orgId),
  });
}

export function useOperationalExceptions() {
  return useQuery({
    queryKey: ['super-admin', 'operational-exceptions'],
    queryFn: async () =>
      (await httpClient.get<ApiResponse<{ exceptions: OperationalException[] }>>('/api/admin/operational-exceptions'))
        .data.data.exceptions,
    refetchInterval: 60_000,
  });
}

export function useOperationalAnalytics() {
  return useQuery({
    queryKey: ['super-admin', 'operational-analytics'],
    queryFn: async () =>
      (await httpClient.get<ApiResponse<OperationalAnalytics>>('/api/admin/operational-analytics')).data.data,
    refetchInterval: 5 * 60_000,
  });
}

export function useAccessChanges(orgId?: string, status?: string) {
  return useQuery({
    queryKey: ['super-admin', 'access-changes', orgId, status],
    queryFn: async () =>
      (
        await httpClient.get<ApiResponse<{ changes: AccessChange[] }>>('/api/admin/access-changes', {
          params: { org_id: orgId, status },
        })
      ).data.data.changes,
  });
}

export function useCommercialRecords(orgId?: string, status?: string) {
  return useQuery({
    queryKey: ['super-admin', 'commercial-records', orgId, status],
    queryFn: async () =>
      (
        await httpClient.get<ApiResponse<{ records: CommercialRecord[] }>>('/api/admin/commercial-records', {
          params: { org_id: orgId, status },
        })
      ).data.data.records,
  });
}

export function useAdminAssignments(enabled = true) {
  return useQuery({
    queryKey: ['super-admin', 'admin-assignments'],
    queryFn: async () =>
      (await httpClient.get<ApiResponse<{ assignments: PlatformAdminAssignment[] }>>('/api/admin/admin-assignments'))
        .data.data.assignments,
    enabled,
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

export function useAdminAuditLogs(enabled = true) {
  return useQuery({
    queryKey: ['super-admin', 'audit-logs'],
    queryFn: async () =>
      (await httpClient.get<ApiResponse<AuditLog[]>>('/api/admin/audit-logs', { params: { limit: 100 } })).data.data,
    enabled,
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

export function useBatchDecideSubscriptionRequests() {
  return useAdminMutation(
    async (body: {
      request_ids: string[];
      decision: string;
      reason: string;
      plan?: string;
      expires_at?: string;
    }) => httpClient.post('/api/admin/subscription-requests/batch-decision', body),
  );
}

export function useSetOrganizationAccess() {
  return useAdminMutation(
    async ({ orgId, ...body }: { orgId: string; plan: string; expires_at?: string | null; reason: string }) =>
      httpClient.put(`/api/admin/organizations/${orgId}/access`, body),
  );
}

export function useScheduleOrganizationAccess() {
  return useAdminMutation(
    async ({
      orgId,
      ...body
    }: {
      orgId: string;
      plan: string;
      expires_at?: string | null;
      effective_at?: string | null;
      reason: string;
      commercial_record_id?: string | null;
    }) => httpClient.post(`/api/admin/organizations/${orgId}/access/schedule`, body),
  );
}

export function useAccessChangeAction() {
  return useAdminMutation(
    async ({ changeId, action, reason }: { changeId: string; action: 'cancel' | 'rollback'; reason: string }) =>
      httpClient.post(`/api/admin/access-changes/${changeId}/${action}`, { reason }),
  );
}

export function useUpsertCommercialRecord() {
  return useAdminMutation(async (body: Partial<CommercialRecord> & { org_id: string; order_number: string }) =>
    httpClient.post('/api/admin/commercial-records', body),
  );
}

export function useSetAdminAssignment() {
  return useAdminMutation(
    async (body: { user_id: string; admin_role: string; permissions: string[]; active: boolean }) =>
      httpClient.put(`/api/admin/admin-assignments/${body.user_id}`, body),
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
