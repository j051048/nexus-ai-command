import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthContext';
import { httpClient } from '@/lib/httpClient';

export interface SalesMetric {
  id: string;
  organization_id: string;
  date: string;
  revenue: number;
  leads_count: number;
  conversions: number;
  win_rate: number;
  user_id: string | null;
  created_at: string;
}

export interface SalesTarget {
  id: string;
  target_type: 'monthly' | 'quarterly';
  target_period: string;
  revenue_target: number;
  leads_target: number;
  conversions_target: number;
  win_rate_target: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface TargetProgress {
  target: SalesTarget;
  current: {
    revenue: number;
    leads: number;
    conversions: number;
    win_rate: number;
  };
  progress: {
    revenue: number;
    leads: number;
    conversions: number;
    win_rate: number;
  };
}

// Fetch current month/quarter targets
export function useCurrentTargets() {
  const { profile } = useAuth();

  return useQuery({
    queryKey: ['sales-targets', 'current', profile?.organization_id],
    queryFn: async () => {
      const response = await httpClient.get('/api/sales/targets');
      return response.data?.targets || [];
    },
    enabled: !!profile?.organization_id
  });
}

// Fetch all targets
export function useAllTargets() {
  const { profile } = useAuth();
  return useQuery({
    queryKey: ['sales-targets', 'all', profile?.organization_id],
    queryFn: async () => {
      const response = await httpClient.get('/api/sales/targets');
      return response.data?.targets || [];
    },
    enabled: !!profile?.organization_id
  });
}

// Create/update target
export function useUpsertTarget() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (target: Omit<SalesTarget, 'id' | 'created_at' | 'updated_at' | 'created_by'>) => {
      const response = await httpClient.post('/api/sales/targets', target);
      return response.data?.target;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales-targets'] });
    },
  });
}

// Delete target
export function useDeleteTarget() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (targetId: string) => {
      await httpClient.delete(`/api/sales/targets/${targetId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales-targets'] });
    },
  });
}

// Get target progress with actual metrics
export function useTargetProgress(targetPeriod: string, targetType: 'monthly' | 'quarterly') {
  const { profile } = useAuth();

  return useQuery({
    queryKey: ['target-progress', targetPeriod, targetType, profile?.organization_id],
    queryFn: async () => {
      const response = await httpClient.get(`/api/sales/metrics?period=${targetPeriod}&type=${targetType}`);
      return response.data?.progress || null;
    },
    enabled: !!profile?.organization_id
  });
}
