import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthContext';
import { approvalRequestSchema, ApprovalRequestSafe } from '@/lib/schemas';
import { aiClient } from '@/api/aiClient';
import { toast } from 'sonner';
import { httpClient } from '@/lib/httpClient';

export type ApprovalRequest = ApprovalRequestSafe;

export function useApprovals() {
  const { user, profile, role } = useAuth();
  const queryClient = useQueryClient();

  const isBoss = role === 'boss';

  // Fetch pending approvals (for Boss)
  const { data: pendingApprovals = [], isLoading } = useQuery({
    queryKey: ['approvals', 'pending', profile?.organization_id],
    queryFn: async () => {
      if (!profile?.organization_id) return [];

      const response = await httpClient.get('/api/approval/list', {
        params: { tab: 'pending' },
      });

      const items = Array.isArray(response.data?.data?.items) ? response.data.data.items : [];

      return items.map((item: Record<string, unknown>) => {
        const dataToValidate = {
          ...item,
          submitter_name: (item.submitter_name as string) || '未知用户',
        };
        const result = approvalRequestSchema.safeParse(dataToValidate);
        return (result.success ? result.data : dataToValidate) as ApprovalRequestSafe;
      });
    },
    enabled: isBoss && !!profile?.organization_id,
  });

  const updateStatus = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: 'approved' | 'rejected' }) => {
      await httpClient.post(`/api/approval/${id}/advance`, { decision: status });
      return { id, status };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
    onError: (error: Error) => {
      toast.error(error.message || '审批操作失败，请重试');
    },
  });

  return {
    pendingApprovals,
    isLoading,
    updateStatus,
  };
}

export function useMyApprovals() {
  const { user, profile } = useAuth();
  return useQuery({
    queryKey: ['approvals', 'me', user?.id, profile?.organization_id],
    queryFn: async () => {
      if (!user?.id) return [];

      const response = await httpClient.get('/api/approval/list', {
        params: { tab: 'mine' },
      });

      const result = response.data?.data?.items;
      return (Array.isArray(result) ? result : []) as ApprovalRequest[];
    },
    enabled: !!user?.id && !!profile?.organization_id,
  });
}

export function useAllApprovals(statusFilter: string = 'all') {
  const { profile } = useAuth();
  return useQuery({
    queryKey: ['approvals', 'all', statusFilter, profile?.organization_id],
    queryFn: async () => {
      if (!profile?.organization_id) return [];

      const params: Record<string, string> = { tab: 'handled' };
      if (statusFilter !== 'all') {
        params.type_filter = statusFilter;
      }

      const response = await httpClient.get('/api/approval/list', { params });

      const items = Array.isArray(response.data?.data?.items) ? response.data.data.items : [];
      return items.map((item: Record<string, unknown>) => ({
        ...item,
        submitter_name: (item.submitter_name as string) || '未知用户',
      })) as ApprovalRequest[];
    },
    enabled: !!profile?.organization_id,
  });
}

export function useSubmitApproval() {
  const { user, profile } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { type: string; description: string; amount: number }) => {
      if (!user?.id) throw new Error('未登录');
      if (!profile?.organization_id) throw new Error('缺少组织信息，无法提交申请');

      const response = await httpClient.post('/api/approval/submit-with-form', {
        type: payload.type,
        amount: payload.amount || 0,
        details: payload.description,
        form_data: {},
      });

      return response.data?.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    }
  });
}

export function useApproveRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (requestId: string) => {
      await httpClient.post(`/api/approval/${requestId}/advance`, { decision: 'approved' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    }
  });
}

export function useRejectRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ requestId, reason }: { requestId: string; reason: string }) => {
      await httpClient.post(`/api/approval/${requestId}/advance`, {
        decision: 'rejected',
        comment: reason,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    }
  });
}

export function useApprovalsRealtime() {
  const queryClient = useQueryClient();
  const { user, profile } = useAuth();

  // Replace Supabase realtime with polling via refetchInterval on related queries
  useQuery({
    queryKey: ['approvals', 'realtime-poll', profile?.organization_id],
    queryFn: async () => {
      // Just trigger invalidation of approval queries
      queryClient.invalidateQueries({ queryKey: ['approvals', 'pending'] });
      queryClient.invalidateQueries({ queryKey: ['approvals', 'me'] });
      queryClient.invalidateQueries({ queryKey: ['approvals', 'all'] });
      return null;
    },
    enabled: !!user?.id && !!profile?.organization_id,
    refetchInterval: 30000, // 30 seconds
  });
}

// ---- P1: Approval Progress Tracker hooks ----

export function useApprovalProgress(requestId: string) {
  return useQuery({
    queryKey: ['approval-progress', requestId],
    queryFn: async () => {
      const result = await aiClient.fetch<{
        steps: Array<{
          id: string;
          type: string;
          label: string;
          role?: string;
          timeout_hours?: number;
        }>;
        current_step: number;
        approval_history: Array<{
          step: number;
          decision: string;
          approver_id: string;
          approver_name?: string;
          timestamp: string;
        }>;
        status: 'pending' | 'approved' | 'rejected';
        risk_analysis?: {
          risk_score: number;
          compliance_flags: string[];
          historical_context: string;
        };
      }>(`api/approval/${requestId}/progress`);
      return result;
    },
    enabled: !!requestId,
  });
}

export function useAdvanceApproval() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      requestId,
      decision,
      comment,
    }: {
      requestId: string;
      decision: 'approved' | 'rejected';
      comment?: string;
    }) => {
      const result = await aiClient.fetch<{ success: boolean }>(
        `api/approval/${requestId}/advance`,
        {
          method: 'POST',
          body: JSON.stringify({ decision, comment }),
        }
      );
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['approval-progress'] });
    },
  });
}


export function usePendingApprovalsCount() {
  const { profile } = useAuth();
  return useQuery({
    queryKey: ['approvals', 'pending-count', profile?.organization_id],
    queryFn: async () => {
      if (!profile?.organization_id) return 0;

      const response = await httpClient.get('/api/approval/tab-counts');
      return response.data?.data?.pending || 0;
    }
  });
}

export function useUrgeApproval() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (requestId: string) => {
      const result = await aiClient.fetch<{ success: boolean; message?: string }>(
        `api/approval/${requestId}/urge`,
        {
          method: 'POST',
        }
      );
      return result;
    },
    onSuccess: (data) => {
      toast.success(data.message || '已成功提醒审批人');
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['approval-progress'] });
    },
    onError: (error: Error) => {
      toast.error('催办失败: ' + error.message);
    }
  });
}

