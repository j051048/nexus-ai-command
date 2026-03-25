import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';

export interface Employee {
  id: string;
  user_id: string;
  name: string;
  avatar: string | null;
  department: string | null;
  job_title: string | null;
  employee_number: string | null;
  score: number;
  rank: number;
  total_bonus: number;
  created_at: string;
  role: 'boss' | 'ai_assistant' | 'manager' | 'employee';
}

// Fetch all employees (for boss)
export function useAllEmployees() {
  const { profile } = useAuth(); // Need profile for organization_id
  
  return useQuery({
    queryKey: ['employees', 'all', profile?.organization_id],
    queryFn: async () => {
      // Get users from public.users table (which now includes role and profile info)
      if (!profile?.organization_id) return [];

      const { data: users, error } = await supabase
        .from('users')
        .select('*')
        .eq('organization_id', profile.organization_id)
        .order('name', { ascending: true }) as any;

      if (error) throw error;

      return (users || []).map((u: any) => ({
        id: u.id,
        user_id: u.id,
        name: u.name,
        avatar: u.avatar,
        department: u.department,
        job_title: u.job_title || null,
        employee_number: u.employee_number || null,
        score: u.score || 0,
        rank: u.rank || 0,
        total_bonus: u.total_bonus || 0,
        created_at: u.created_at,
        role: (u.role === 'founder' || u.role === 'boss' ? 'boss' :
              u.role === 'ai_assistant' ? 'ai_assistant' :
              u.role === 'manager' ? 'manager' : 'employee') as Employee['role'],
      })) as Employee[];
    },
    enabled: !!profile?.organization_id // Only run if we know the org
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
      // Use the RPC for atomic transfer
      const { error } = await (supabase as any).rpc('transfer_employee_data', {
        from_user_id: fromUserId,
        to_user_id: toUserId,
      });

      if (error) throw error;
      return { fromUserId, toUserId };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      queryClient.invalidateQueries({ queryKey: ['employee-stats'] });
    },
  });
}

// Delete employee (remove from public.users)
export function useDeleteEmployee() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (userId: string) => {
      // Use the RPC for deletion
      const { error } = await (supabase as any).rpc('delete_employee', {
        target_user_id: userId,
      });

      if (error) throw error;
      return userId;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
    },
  });
}

// Update employee profile (via admin_update_user RPC to bypass RLS)
export function useUpdateEmployee() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      userId,
      updates
    }: {
      userId: string;
      updates: Partial<Pick<Employee, 'name' | 'department' | 'job_title' | 'employee_number' | 'score' | 'total_bonus' | 'role'>>;
    }) => {
      const { data, error } = await (supabase as any).rpc('admin_update_user', {
        target_user_id: userId,
        new_role: updates.role ?? null,
        new_department: updates.department ?? null,
        new_job_title: updates.job_title ?? null,
        new_employee_number: updates.employee_number ?? null,
      });

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

// Fetch departments list for dropdown
export function useDepartments() {
  const { profile } = useAuth();
  
  return useQuery({
    queryKey: ['departments', profile?.organization_id],
    queryFn: async () => {
      if (!profile?.organization_id) return [];
      
      const { data, error } = await supabase
        .from('departments')
        .select('id, name')
        .eq('organization_id', profile.organization_id)
        .eq('status', 'active')
        .order('name', { ascending: true });
        
      if (error) throw error;
      return (data || []) as { id: string; name: string }[];
    },
    enabled: !!profile?.organization_id
  });
}
