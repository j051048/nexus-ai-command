import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';
import { approvalRequestSchema, ApprovalRequestSafe } from '@/lib/schemas';
import { useEffect } from 'react';
import { aiClient } from '@/api/aiClient';

export type ApprovalRequest = ApprovalRequestSafe;

export function useApprovals() {
  const { user, profile } = useAuth();
  const queryClient = useQueryClient();

  const isBoss = user?.role === 'boss';

  // Fetch pending approvals (for Boss)
  const { data: pendingApprovals = [], isLoading } = useQuery({
    queryKey: ['approvals', 'pending', profile?.organization_id],
    queryFn: async () => {
      if (!profile?.organization_id) return [];
      
      const { data, error } = await supabase
        .from('approval_requests')
        .select(`
          *,
          users:submitted_by ( name )
        `)
        .eq('status', 'pending')
        .eq('organization_id', profile.organization_id)
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
    enabled: isBoss && !!profile?.organization_id,
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
  const { user, profile } = useAuth();
  return useQuery({
    queryKey: ['approvals', 'me', user?.id, profile?.organization_id],
    queryFn: async () => {
      if (!user?.id) return [];
      
      // 查询所有与当前用户相关的审批记录
      // 包括：直接提交的 + AI代提交的（on_behalf_of）
      const { data, error } = await supabase
        .from('approval_requests')
        .select('*')
        .eq('organization_id', profile?.organization_id)
        .or(`submitted_by.eq.${user.id},on_behalf_of.eq.${user.id}`)
        .order('created_at', { ascending: false });

      if (error) {
        console.error('Error fetching my approvals:', error);
        throw error;
      }
      return data as ApprovalRequest[];
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

      let query = supabase
        .from('approval_requests')
        .select('*, users:submitted_by(name)')
        .eq('organization_id', profile.organization_id)
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

      // Task A: AI Orchestration Layer - Call Backend
      let decision = 'pending';
      let aiReason = '正在等待系统分析...';

      try {
        const result = await aiClient.processApproval({
          requester_id: user.id,
          type: payload.type,
          amount: payload.amount,
          details: payload.description
        });

        decision = result.decision === 'auto_approved' ? 'approved' : 'pending';
        aiReason = result.reason;
      } catch (err) {
        console.warn('AI Orchestration layer unavailable or failed:', err);
        aiReason = 'AI 服务暂时下线，已转入人工审批队列';
      }

      const { data, error } = await supabase
        .from('approval_requests')
        .insert({
          submitted_by: user.id,
          organization_id: profile?.organization_id, // P0 Fix: Force org isolation
          type: payload.type,
          description: payload.description,
          amount: payload.amount,
          status: decision as 'pending' | 'approved' | 'rejected',
          ai_reason: aiReason,
          submitted_at: new Date().toISOString()
        })
        .select()
        .single();

      if (error) throw error;
      return { ...data, auto_approved: decision === 'approved' };
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
  const { user, profile } = useAuth();

  useEffect(() => {
    if (!user?.id || !profile?.organization_id) return;

    const channel = supabase
      .channel('approvals-realtime')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'approval_requests',
          filter: `organization_id=eq.${profile.organization_id}`,
        },
        () => {
          queryClient.invalidateQueries({ queryKey: ['approvals'] });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [user?.id, profile?.organization_id, queryClient]);
}

export function usePendingApprovalsCount() {
  const { profile } = useAuth();
  return useQuery({
    queryKey: ['approvals', 'pending-count', profile?.organization_id],
    queryFn: async () => {
      if (!profile?.organization_id) return 0;
      
      const { count, error } = await supabase
        .from('approval_requests')
        .select('*', { count: 'exact', head: true })
        .eq('status', 'pending')
        .eq('organization_id', profile.organization_id);

      if (error) throw error;
      return count || 0;
    }
  });
}
