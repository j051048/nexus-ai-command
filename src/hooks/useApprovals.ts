import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';

export interface ApprovalRequest {
  id: string;
  submitted_by: string;
  type: string;
  amount: number;
  description: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  submitter_name?: string; // We will join this
}

export function useApprovals() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const isBoss = user?.role === 'boss';

  // Fetch pending approvals (for Boss)
  const { data: pendingApprovals = [], isLoading } = useQuery({
    queryKey: ['approvals', 'pending'],
    queryFn: async () => {
      // We need to join with profiles/users to get names
      // Since supabase-js join syntax is specific, and we're using raw tables, 
      // let's do a simple select.

      const { data, error } = await supabase
        .from('approval_requests')
        .select(`
          *,
          users:submitted_by ( name )
        `)
        .eq('status', 'pending')
        .order('created_at', { ascending: false });

      if (error) throw error;

      return data.map((item: any) => ({
        ...item,
        submitter_name: item.users?.name || 'Unknown',
      })) as ApprovalRequest[];
    },
    enabled: isBoss, // Only boss needs to see pending list for now
  });

  // Approve/Reject Mutation
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
      // Optimistic update or refetch
      queryClient.setQueryData(['approvals', 'pending'], (old: ApprovalRequest[] | undefined) => {
        return old?.filter(req => req.id !== variables.id) || [];
      });
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
  });

  return {
    pendingApprovals,
    isLoading,
    updateStatus,
  };
}
