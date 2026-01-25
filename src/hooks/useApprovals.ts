import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';
import { approvalRequestSchema, ApprovalRequestSafe } from '@/lib/schemas';
import { useEffect } from 'react';

export type ApprovalRequest = ApprovalRequestSafe;

export function useApprovals() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const isBoss = user?.role === 'boss';

  // Fetch pending approvals (for Boss)
  const { data: pendingApprovals = [], isLoading } = useQuery({
    queryKey: ['approvals', 'pending'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('approval_requests')
        .select(`
          *,
          users:submitted_by ( name )
        `)
        .eq('status', 'pending')
        .order('created_at', { ascending: false });

      if (error) {
        console.error('Error fetching approvals:', error);
        return [];
      }

      return (data || []).map((item) => {
        const dataToValidate = {
          ...item,
          submitter_name: (item as unknown as { users: { name: string } | null }).users?.name || '未知用户',
        };
        const result = approvalRequestSchema.safeParse(dataToValidate);
        return (result.success ? result.data : dataToValidate) as ApprovalRequestSafe;
      });
    },
    enabled: isBoss,
  });

  const updateStatus = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: 'approved' | 'rejected' }) => {
      const { error } = await supabase
        .from('approval_requests')
        .update({ status })
        .eq('id', id);

      if (error) throw error;
      return { id, status };
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
  });

  return {
    pendingApprovals,
    isLoading,
    updateStatus,
  };
}

export function useMyApprovals() {
  const { user } = useAuth();
  return useQuery({
    queryKey: ['approvals', 'me', user?.id],
    queryFn: async () => {
      if (!user?.id) return [];
      const { data, error } = await supabase
        .from('approval_requests')
        .select('*')
        .eq('submitted_by', user.id)
        .order('submitted_at', { ascending: false });

      if (error) throw error;
      return data as ApprovalRequest[];
    },
    enabled: !!user?.id,
  });
}

export function useAllApprovals(statusFilter: string = 'all') {
  return useQuery({
    queryKey: ['approvals', 'all', statusFilter],
    queryFn: async () => {
      let query = supabase
        .from('approval_requests')
        .select('*, users:submitted_by(name)')
        .order('submitted_at', { ascending: false });

      if (statusFilter !== 'all') {
        query = query.eq('status', statusFilter);
      }

      const { data, error } = await query;
      if (error) throw error;

      return (data || []).map((item) => ({
        ...item,
        submitter_name: (item as unknown as { users: { name: string } | null }).users?.name || '未知用户',
      })) as ApprovalRequest[];
    },
  });
}

export function useSubmitApproval() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { type: string; description: string; amount: number }) => {
      if (!user?.id) throw new Error('未登录');

      // Simple AI logic: auto approve if amount is small
      const thresholdMap: Record<string, number> = {
        travel: 3000,
        purchase: 5000,
        expense: 500,
        leave: 3
      };

      const threshold = thresholdMap[payload.type] || 0;
      const isAutoApproved = payload.amount <= threshold;
      const status = isAutoApproved ? 'approved' : 'pending';

      const { data, error } = await supabase
        .from('approval_requests')
        .insert({
          submitted_by: user.id,
          type: payload.type,
          description: payload.description,
          amount: payload.amount,
          status: status,
          ai_reason: isAutoApproved ? '金额在预设阈值内，系统自动通过' : '金额较大，需要人工干预',
          submitted_at: new Date().toISOString()
        })
        .select()
        .single();

      if (error) throw error;
      return { ...data, auto_approved: isAutoApproved };
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
      const { error } = await supabase
        .from('approval_requests')
        .update({ status: 'approved' })
        .eq('id', requestId);
      if (error) throw error;
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
      const { error } = await supabase
        .from('approval_requests')
        .update({
          status: 'rejected',
          rejection_reason: reason
        })
        .eq('id', requestId);
      if (error) throw error;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    }
  });
}

export function useApprovalsRealtime() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  useEffect(() => {
    if (!user?.id) return;

    const channel = supabase
      .channel('approvals-realtime')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'approval_requests' },
        () => {
          queryClient.invalidateQueries({ queryKey: ['approvals'] });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [user?.id, queryClient]);
}

export function usePendingApprovalsCount() {
  return useQuery({
    queryKey: ['approvals', 'pending-count'],
    queryFn: async () => {
      const { count, error } = await supabase
        .from('approval_requests')
        .select('*', { count: 'exact', head: true })
        .eq('status', 'pending');

      if (error) throw error;
      return count || 0;
    }
  });
}
