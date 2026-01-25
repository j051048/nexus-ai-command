import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';
import { useEffect } from 'react';

export interface ApprovalRequest {
  id: string;
  type: 'travel' | 'purchase' | 'expense' | 'leave' | 'activity';
  description: string;
  amount: number;
  status: 'pending' | 'auto_approved' | 'requires_boss' | 'approved' | 'rejected';
  submitted_by: string;
  submitted_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  ai_reason: string | null;
  rejection_reason: string | null;
  metadata: Record<string, any>;
  // Joined data
  submitter_name?: string;
}

export interface Notification {
  id: string;
  user_id: string;
  type: string;
  title: string;
  message: string;
  read: boolean;
  data: Record<string, any>;
  created_at: string;
}

// AI approval thresholds (can be configured)
const APPROVAL_THRESHOLDS = {
  travel: 3000,
  purchase: 5000,
  expense: 500,
  leave: 3, // days
  activity: 2000,
};

// Fetch user's approvals
export function useMyApprovals() {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['approvals', 'my', user?.id],
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

// Fetch all approvals (for boss)
export function useAllApprovals(statusFilter?: string) {
  return useQuery({
    queryKey: ['approvals', 'all', statusFilter],
    queryFn: async () => {
      let query = supabase
        .from('approval_requests')
        .select('*')
        .order('submitted_at', { ascending: false });

      if (statusFilter && statusFilter !== 'all') {
        query = query.eq('status', statusFilter);
      }

      const { data, error } = await query;
      if (error) throw error;

      // Get submitter names
      const submitterIds = [...new Set(data?.map(a => a.submitted_by) || [])];
      const { data: profiles } = await supabase
        .from('profiles')
        .select('user_id, name')
        .in('user_id', submitterIds);

      const nameMap = new Map(profiles?.map(p => [p.user_id, p.name]));

      return (data || []).map(a => ({
        ...a,
        submitter_name: nameMap.get(a.submitted_by) || '未知',
      })) as ApprovalRequest[];
    },
  });
}

// Fetch pending approvals count (for boss badge)
export function usePendingApprovalsCount() {
  return useQuery({
    queryKey: ['approvals', 'pending-count'],
    queryFn: async () => {
      const { count, error } = await supabase
        .from('approval_requests')
        .select('*', { count: 'exact', head: true })
        .eq('status', 'requires_boss');

      if (error) throw error;
      return count || 0;
    },
  });
}

// Submit approval request with AI auto-processing
export function useSubmitApproval() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  return useMutation({
    mutationFn: async (request: {
      type: 'travel' | 'purchase' | 'expense' | 'leave' | 'activity';
      description: string;
      amount: number;
      metadata?: Record<string, any>;
    }) => {
      if (!user?.id) throw new Error('未登录');

      // AI auto-approval logic
      const threshold = APPROVAL_THRESHOLDS[request.type];
      const shouldAutoApprove = request.amount <= threshold;

      const status = shouldAutoApprove ? 'auto_approved' : 'requires_boss';
      const aiReason = shouldAutoApprove
        ? `金额 ¥${request.amount} 在自动审批阈值 ¥${threshold} 范围内，已自动通过`
        : `金额 ¥${request.amount} 超过自动审批阈值 ¥${threshold}，需老板审批`;

      const { data, error } = await supabase
        .from('approval_requests')
        .insert({
          type: request.type,
          description: request.description,
          amount: request.amount,
          status,
          submitted_by: user.id,
          ai_reason: aiReason,
          metadata: request.metadata || {},
        })
        .select()
        .single();

      if (error) throw error;
      return { ...data, auto_approved: shouldAutoApprove };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
  });
}

// Boss approve request
export function useApproveRequest() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  return useMutation({
    mutationFn: async (requestId: string) => {
      if (!user?.id) throw new Error('未登录');

      // Get the approval request first
      const { data: request, error: fetchError } = await supabase
        .from('approval_requests')
        .select('submitted_by, description, type')
        .eq('id', requestId)
        .single();

      if (fetchError) throw fetchError;

      // Update approval status
      const { error } = await supabase
        .from('approval_requests')
        .update({
          status: 'approved',
          reviewed_by: user.id,
          reviewed_at: new Date().toISOString(),
        })
        .eq('id', requestId);

      if (error) throw error;

      // Create notification for the submitter
      await supabase
        .from('notifications')
        .insert({
          user_id: request.submitted_by,
          type: 'approval_approved',
          title: '审批已通过',
          message: `您的${getTypeLabel(request.type)}申请「${request.description}」已被批准`,
          data: { approval_id: requestId },
        });

      return requestId;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
  });
}

// Boss reject request
export function useRejectRequest() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  return useMutation({
    mutationFn: async ({ requestId, reason }: { requestId: string; reason: string }) => {
      if (!user?.id) throw new Error('未登录');

      // Get the approval request first
      const { data: request, error: fetchError } = await supabase
        .from('approval_requests')
        .select('submitted_by, description, type')
        .eq('id', requestId)
        .single();

      if (fetchError) throw fetchError;

      // Update approval status
      const { error } = await supabase
        .from('approval_requests')
        .update({
          status: 'rejected',
          reviewed_by: user.id,
          reviewed_at: new Date().toISOString(),
          rejection_reason: reason,
        })
        .eq('id', requestId);

      if (error) throw error;

      // Create notification for the submitter
      await supabase
        .from('notifications')
        .insert({
          user_id: request.submitted_by,
          type: 'approval_rejected',
          title: '审批被驳回',
          message: `您的${getTypeLabel(request.type)}申请「${request.description}」被驳回，原因：${reason}`,
          data: { approval_id: requestId, reason },
        });

      return requestId;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
  });
}

// Fetch user notifications
export function useNotifications() {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['notifications', user?.id],
    queryFn: async () => {
      if (!user?.id) return [];

      const { data, error } = await supabase
        .from('notifications')
        .select('*')
        .eq('user_id', user.id)
        .order('created_at', { ascending: false })
        .limit(50);

      if (error) throw error;
      return data as Notification[];
    },
    enabled: !!user?.id,
  });
}

// Mark notification as read
export function useMarkNotificationRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (notificationId: string) => {
      const { error } = await supabase
        .from('notifications')
        .update({ read: true })
        .eq('id', notificationId);

      if (error) throw error;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

// Realtime subscription for approvals
export function useApprovalsRealtime() {
  const queryClient = useQueryClient();

  useEffect(() => {
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
  }, [queryClient]);
}

// Realtime subscription for notifications
export function useNotificationsRealtime() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  useEffect(() => {
    if (!user?.id) return;

    const channel = supabase
      .channel('notifications-realtime')
      .on(
        'postgres_changes',
        { 
          event: 'INSERT', 
          schema: 'public', 
          table: 'notifications',
          filter: `user_id=eq.${user.id}`,
        },
        () => {
          queryClient.invalidateQueries({ queryKey: ['notifications'] });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [queryClient, user?.id]);
}

// Helper function
function getTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    travel: '出差',
    purchase: '采购',
    expense: '报销',
    leave: '请假',
    activity: '活动',
  };
  return labels[type] || type;
}
