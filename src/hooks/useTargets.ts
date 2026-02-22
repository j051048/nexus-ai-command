import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';

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
  const currentMonth = new Date().toISOString().slice(0, 7); // 2026-01
  const currentQuarter = `${new Date().getFullYear()}-Q${Math.ceil((new Date().getMonth() + 1) / 3)}`;

  return useQuery({
    queryKey: ['sales-targets', 'current', profile?.organization_id],
    queryFn: async () => {
      const query = supabase.from('sales_targets');

      const { data, error } = await query
        .select('*')
        .eq('organization_id', profile?.organization_id)
        .or(`target_period.eq.${currentMonth},target_period.eq.${currentQuarter}`)
        .order('created_at', { ascending: false });

      if (error) throw error;
      return data as SalesTarget[];
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
      const { data, error } = await supabase
        .from('sales_targets')
        .select('*')
        .eq('organization_id', profile?.organization_id)
        .order('target_period', { ascending: false });

      if (error) throw error;
      return data as SalesTarget[];
    },
    enabled: !!profile?.organization_id
  });
}

// Create/update target
export function useUpsertTarget() {
  const queryClient = useQueryClient();
  const { user, profile } = useAuth();

  return useMutation({
    mutationFn: async (target: Omit<SalesTarget, 'id' | 'created_at' | 'updated_at' | 'created_by'>) => {
      if (!profile?.organization_id) throw new Error("Organization ID missing");

      // Check if target already exists for this period
      const { data: existing } = await supabase
        .from('sales_targets')
        .select('id')
        .eq('organization_id', profile.organization_id)
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
            organization_id: profile.organization_id, // Add org_id
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
  const { profile } = useAuth();

  return useQuery({
    queryKey: ['target-progress', targetPeriod, targetType, profile?.organization_id],
    queryFn: async () => {
      // Get target
      const { data: target, error: targetError } = await supabase
        .from('sales_targets')
        .select('*')
        .eq('organization_id', profile?.organization_id)
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
      // Note: sales_metrics currently not filtered by org in query, but RLS might limit it.
      // However, to be safe, we should probably filter by user list in org or add org_id to sales_metrics if possible.
      // For now, assuming sales_metrics has org_id or RLS handles it. 
      // Based on useSalesData.ts update, sales_metrics HAS org_id.

      let metricsQuery = supabase.from('sales_metrics');
      
      if (profile?.organization_id) {
         metricsQuery = metricsQuery.select('*').eq('organization_id', profile.organization_id);
      } else {
         metricsQuery = metricsQuery.select('*');
      }

      const { data: metrics, error: metricsError } = await metricsQuery;

      if (metricsError) throw metricsError;

      // Filter by date range manually
      const rawMetrics = (metrics || []) as unknown as SalesMetric[];
      const filteredMetrics = rawMetrics.filter((m) => {
          const d = m.date;
          return d >= startDate && d <= endDate;
      });

      // Calculate totals
      const current = {
        revenue: filteredMetrics.reduce((sum, m) => sum + (Number(m.revenue) || 0), 0),
        leads: filteredMetrics.reduce((sum, m) => sum + (Number(m.leads_count) || 0), 0),
        conversions: filteredMetrics.reduce((sum, m) => sum + (Number(m.conversions) || 0), 0),
        win_rate: filteredMetrics.length
          ? filteredMetrics.reduce((sum, m) => sum + (Number(m.win_rate) || 0), 0) / filteredMetrics.length
          : 0,
      };

      // Calculate progress percentages
      const progress = {
        revenue: target.revenue_target > 0 ? (current.revenue / Number(target.revenue_target)) * 100 : 0,
        leads: target.leads_target > 0 ? (current.leads / Number(target.leads_target)) * 100 : 0,
        conversions: target.conversions_target > 0 ? (current.conversions / Number(target.conversions_target)) * 100 : 0,
        win_rate: target.win_rate_target > 0 ? (current.win_rate / Number(target.win_rate_target)) * 100 : 0,
      };

      return {
        target: target as SalesTarget,
        current,
        progress,
      } as TargetProgress;
    },
    enabled: !!profile?.organization_id
  });
}
