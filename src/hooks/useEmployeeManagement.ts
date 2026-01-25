import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';

export interface Employee {
  id: string;
  user_id: string;
  name: string;
  avatar: string | null;
  department: string | null;
  score: number;
  rank: number;
  total_bonus: number;
  created_at: string;
  role: 'boss' | 'employee';
}

// Fetch all employees (for boss)
export function useAllEmployees() {
  return useQuery({
    queryKey: ['employees', 'all'],
    queryFn: async () => {
      // Get users from public.users table (which now includes role and profile info)
      const { data: users, error } = await supabase
        .from('users')
        .select('*')
        .order('name', { ascending: true });

      if (error) throw error;

      // Cast to any to bypass strict type check on 'users' table which might not be fully generated in types yet
      return (users as any[] || []).map(u => ({
        id: u.id,
        user_id: u.id,
        name: u.name,
        avatar: u.avatar,
        department: u.department,
        score: u.score || 0,
        rank: u.rank || 0,
        total_bonus: u.total_bonus || 0,
        created_at: u.created_at,
        role: (u.role === 'founder' ? 'boss' : 'employee') as 'boss' | 'employee',
      })) as Employee[];
    },
  });
}

// Transfer employee data to another employee
export function useTransferEmployeeData() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      fromUserId,
      toUserId
    }: {
      fromUserId: string;
      toUserId: string;
    }) => {
      // Transfer sales_metrics
      const { error: metricsError } = await supabase
        .from('sales_metrics')
        .update({ user_id: toUserId })
        .eq('user_id', fromUserId);

      if (metricsError) throw metricsError;

      // Transfer badges
      const { error: badgesError } = await supabase
        .from('badges')
        .update({ user_id: toUserId })
        .eq('user_id', fromUserId);

      if (badgesError) throw badgesError;

      // Transfer approval requests
      const { error: approvalsError } = await supabase
        .from('approval_requests')
        .update({ submitted_by: toUserId })
        .eq('submitted_by', fromUserId);

      if (approvalsError) throw approvalsError;

      return { fromUserId, toUserId };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      queryClient.invalidateQueries({ queryKey: ['sales-metrics'] });
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
  });
}

// Delete employee (remove profile and role, but auth.users needs admin API)
export function useDeleteEmployee() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (userId: string) => {
      // Delete from profiles
      const { error: profileError } = await supabase
        .from('profiles')
        .delete()
        .eq('user_id', userId);

      if (profileError) throw profileError;

      // Delete from user_roles
      const { error: roleError } = await supabase
        .from('user_roles')
        .delete()
        .eq('user_id', userId);

      if (roleError) throw roleError;

      // Note: Cannot delete from auth.users directly - would need admin API
      // The user won't be able to access the app anymore after profile deletion

      return userId;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
    },
  });
}

// Update employee profile
export function useUpdateEmployee() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      userId,
      updates
    }: {
      userId: string;
      updates: Partial<Pick<Employee, 'name' | 'department' | 'score' | 'total_bonus'>>;
    }) => {
      const { data, error } = await supabase
        .from('profiles')
        .update(updates)
        .eq('user_id', userId)
        .select()
        .single();

      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
    },
  });
}

// Get employee statistics
export function useEmployeeStats(userId: string) {
  return useQuery({
    queryKey: ['employee-stats', userId],
    queryFn: async () => {
      // Get sales metrics count
      const { count: metricsCount } = await supabase
        .from('sales_metrics')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', userId);

      // Get badges count
      const { count: badgesCount } = await supabase
        .from('badges')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', userId);

      // Get approvals count
      const { count: approvalsCount } = await supabase
        .from('approval_requests')
        .select('*', { count: 'exact', head: true })
        .eq('submitted_by', userId);

      return {
        metricsCount: metricsCount || 0,
        badgesCount: badgesCount || 0,
        approvalsCount: approvalsCount || 0,
      };
    },
    enabled: !!userId,
  });
}
