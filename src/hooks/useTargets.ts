import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';

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
  const currentMonth = new Date().toISOString().slice(0, 7); // 2026-01
  const currentQuarter = `${new Date().getFullYear()}-Q${Math.ceil((new Date().getMonth() + 1) / 3)}`;

  return useQuery({
    queryKey: ['sales-targets', 'current'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('sales_targets')
        .select('*')
        .or(`target_period.eq.${currentMonth},target_period.eq.${currentQuarter}`)
        .order('created_at', { ascending: false });

      if (error) throw error;
      return data as SalesTarget[];
    },
  });
}

// Fetch all targets
export function useAllTargets() {
  return useQuery({
    queryKey: ['sales-targets', 'all'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('sales_targets')
        .select('*')
        .order('target_period', { ascending: false });

      if (error) throw error;
      return data as SalesTarget[];
    },
  });
}

// Create/update target
export function useUpsertTarget() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  return useMutation({
    mutationFn: async (target: Omit<SalesTarget, 'id' | 'created_at' | 'updated_at' | 'created_by'>) => {
      // Check if target already exists for this period
      const { data: existing } = await supabase
        .from('sales_targets')
        .select('id')
        .eq('target_period', target.target_period)
        .eq('target_type', target.target_type)
        .maybeSingle();

      if (existing) {
        // Update existing
        const { data, error } = await supabase
          .from('sales_targets')
          .update({
            revenue_target: target.revenue_target,
            leads_target: target.leads_target,
            conversions_target: target.conversions_target,
            win_rate_target: target.win_rate_target,
          })
          .eq('id', existing.id)
          .select()
          .single();

        if (error) throw error;
        return data;
      } else {
        // Insert new
        const { data, error } = await supabase
          .from('sales_targets')
          .insert({
            ...target,
            created_by: user?.id,
          })
          .select()
          .single();

        if (error) throw error;
        return data;
      }
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
      const { error } = await supabase
        .from('sales_targets')
        .delete()
        .eq('id', targetId);

      if (error) throw error;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales-targets'] });
    },
  });
}

// Get target progress with actual metrics
export function useTargetProgress(targetPeriod: string, targetType: 'monthly' | 'quarterly') {
  return useQuery({
    queryKey: ['target-progress', targetPeriod, targetType],
    queryFn: async () => {
      // Get target
      const { data: target, error: targetError } = await supabase
        .from('sales_targets')
        .select('*')
        .eq('target_period', targetPeriod)
        .eq('target_type', targetType)
        .maybeSingle();

      if (targetError) throw targetError;
      if (!target) return null;

      // Calculate date range for the period
      let startDate: string;
      let endDate: string;

      if (targetType === 'monthly') {
        startDate = `${targetPeriod}-01`;
        const [year, month] = targetPeriod.split('-').map(Number);
        const lastDay = new Date(year, month, 0).getDate();
        endDate = `${targetPeriod}-${lastDay}`;
      } else {
        const [year, quarter] = targetPeriod.split('-Q').map(Number);
        const startMonth = (quarter - 1) * 3 + 1;
        const endMonth = quarter * 3;
        startDate = `${year}-${String(startMonth).padStart(2, '0')}-01`;
        const lastDay = new Date(year, endMonth, 0).getDate();
        endDate = `${year}-${String(endMonth).padStart(2, '0')}-${lastDay}`;
      }

      // Get actual metrics for the period
      const { data: metrics, error: metricsError } = await supabase
        .from('sales_metrics')
        .select('*')
        .gte('date', startDate)
        .lte('date', endDate);

      if (metricsError) throw metricsError;

      // Calculate totals
      const current = {
        revenue: metrics?.reduce((sum, m) => sum + (Number(m.revenue) || 0), 0) || 0,
        leads: metrics?.reduce((sum, m) => sum + (m.leads_count || 0), 0) || 0,
        conversions: metrics?.reduce((sum, m) => sum + (m.conversions || 0), 0) || 0,
        win_rate: metrics?.length 
          ? metrics.reduce((sum, m) => sum + (Number(m.win_rate) || 0), 0) / metrics.length 
          : 0,
      };

      // Calculate progress percentages
      const progress = {
        revenue: target.revenue_target > 0 ? (current.revenue / Number(target.revenue_target)) * 100 : 0,
        leads: target.leads_target > 0 ? (current.leads / target.leads_target) * 100 : 0,
        conversions: target.conversions_target > 0 ? (current.conversions / target.conversions_target) * 100 : 0,
        win_rate: target.win_rate_target > 0 ? (current.win_rate / Number(target.win_rate_target)) * 100 : 0,
      };

      return {
        target: target as SalesTarget,
        current,
        progress,
      } as TargetProgress;
    },
  });
}
