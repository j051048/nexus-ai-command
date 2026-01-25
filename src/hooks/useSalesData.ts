import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';
import { format, subDays, startOfWeek, subWeeks } from 'date-fns';
import { useEffect } from 'react';

export interface SalesMetric {
  id: string;
  user_id: string | null;
  date: string;
  leads_count: number | null;
  conversions: number | null;
  revenue: number | null;
  win_rate: number | null;
  calls_made: number | null;
  score: number | null;
  created_at: string | null;
}

export interface TeamPerformanceData {
  id: string;
  week_start: string;
  total_leads: number | null;
  total_conversions: number | null;
  total_revenue: number | null;
  avg_win_rate: number | null;
  top_performer_id: string | null;
  created_at: string | null;
}

export interface TeamMemberPerformance {
  name: string;
  score: number;
  bonus: number;
  calls: number;
  conversions: number;
  user_id: string;
}

// Hook for real-time subscription to sales metrics
export function useSalesMetricsRealtime() {
  const queryClient = useQueryClient();
  const { session } = useAuth();

  useEffect(() => {
    if (!session?.user?.id) return;

    const channel = supabase
      .channel('sales-metrics-changes')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'sales_metrics',
        },
        (payload) => {
          console.log('Sales metrics changed:', payload);
          // Invalidate all related queries to refetch fresh data
          queryClient.invalidateQueries({ queryKey: ['sales-metrics'] });
          queryClient.invalidateQueries({ queryKey: ['sales-metrics-range'] });
          queryClient.invalidateQueries({ queryKey: ['win-rate-history'] });
          queryClient.invalidateQueries({ queryKey: ['revenue-data'] });
          queryClient.invalidateQueries({ queryKey: ['team-performance'] });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [session?.user?.id, queryClient]);
}

// Fetch user's sales metrics for the last N months
export function useSalesMetrics(months: number = 7) {
  const { session } = useAuth();

  return useQuery({
    queryKey: ['sales-metrics', session?.user?.id, months],
    queryFn: async () => {
      if (!session?.user?.id) return [];

      const startDate = format(subDays(new Date(), months * 30), 'yyyy-MM-dd');
      
      const { data, error } = await supabase
        .from('sales_metrics')
        .select('*')
        .eq('user_id', session.user.id)
        .gte('date', startDate)
        .order('date', { ascending: true });

      if (error) throw error;
      return data as SalesMetric[];
    },
    enabled: !!session?.user?.id,
  });
}

// Fetch sales metrics by date range
export function useSalesMetricsByRange(startDate: string | null, endDate: string | null) {
  const { session, role } = useAuth();

  return useQuery({
    queryKey: ['sales-metrics-range', session?.user?.id, role, startDate, endDate],
    queryFn: async () => {
      if (!session?.user?.id || !startDate || !endDate) return [];

      let query = supabase
        .from('sales_metrics')
        .select('*')
        .gte('date', startDate)
        .lte('date', endDate)
        .order('date', { ascending: false });

      // If not boss, only get own metrics
      if (role !== 'boss') {
        query = query.eq('user_id', session.user.id);
      }

      const { data, error } = await query;
      if (error) throw error;
      return data as SalesMetric[];
    },
    enabled: !!session?.user?.id && !!startDate && !!endDate,
  });
}

// Fetch win rate data by week for the last N weeks
export function useWinRateHistory(weeks: number = 8) {
  const { session } = useAuth();

  return useQuery({
    queryKey: ['win-rate-history', session?.user?.id, weeks],
    queryFn: async () => {
      if (!session?.user?.id) return [];

      const startDate = format(subWeeks(new Date(), weeks), 'yyyy-MM-dd');
      
      const { data, error } = await supabase
        .from('sales_metrics')
        .select('date, win_rate')
        .eq('user_id', session.user.id)
        .gte('date', startDate)
        .order('date', { ascending: true });

      if (error) throw error;
      
      // Group by week and calculate average win rate per week
      const weeklyData: { week: string; rate: number; target: number }[] = [];
      const weekMap = new Map<string, number[]>();
      
      (data || []).forEach((item) => {
        const weekStart = format(startOfWeek(new Date(item.date), { weekStartsOn: 1 }), 'yyyy-MM-dd');
        if (!weekMap.has(weekStart)) {
          weekMap.set(weekStart, []);
        }
        if (item.win_rate !== null) {
          weekMap.get(weekStart)!.push(Number(item.win_rate));
        }
      });

      let weekNum = 1;
      weekMap.forEach((rates, _weekStart) => {
        const avgRate = rates.length > 0 
          ? Math.round(rates.reduce((a, b) => a + b, 0) / rates.length) 
          : 0;
        weeklyData.push({
          week: `第${weekNum}周`,
          rate: avgRate,
          target: 25,
        });
        weekNum++;
      });

      return weeklyData;
    },
    enabled: !!session?.user?.id,
  });
}

// Fetch monthly revenue data
export function useRevenueData(months: number = 7) {
  const { session, role } = useAuth();

  return useQuery({
    queryKey: ['revenue-data', session?.user?.id, role, months],
    queryFn: async () => {
      if (!session?.user?.id) return [];

      const startDate = format(subDays(new Date(), months * 30), 'yyyy-MM-dd');
      
      // If boss, get all metrics; if employee, get own metrics
      let query = supabase
        .from('sales_metrics')
        .select('date, revenue')
        .gte('date', startDate)
        .order('date', { ascending: true });

      if (role !== 'boss') {
        query = query.eq('user_id', session.user.id);
      }

      const { data, error } = await query;
      if (error) throw error;

      // Group by month
      const monthMap = new Map<string, number>();
      const targetPerMonth = 150; // Target in 万

      (data || []).forEach((item) => {
        const monthKey = format(new Date(item.date), 'M月');
        const current = monthMap.get(monthKey) || 0;
        monthMap.set(monthKey, current + (Number(item.revenue) || 0));
      });

      return Array.from(monthMap.entries()).map(([month, revenue]) => ({
        month,
        revenue: Math.round(revenue / 10000), // Convert to 万
        target: targetPerMonth,
        growth: 0, // Could calculate from previous month
      }));
    },
    enabled: !!session?.user?.id,
  });
}

// Fetch team performance data (for boss role)
export function useTeamPerformance() {
  const { session, role } = useAuth();

  return useQuery({
    queryKey: ['team-performance', session?.user?.id],
    queryFn: async () => {
      if (!session?.user?.id) return [];

      // Get all profiles with their scores and bonuses
      const { data: profiles, error: profilesError } = await supabase
        .from('profiles')
        .select('user_id, name, score, total_bonus')
        .order('score', { ascending: false })
        .limit(10);

      if (profilesError) throw profilesError;

      // Get latest sales metrics for each user
      const userIds = (profiles || []).map(p => p.user_id);
      
      const { data: metrics, error: metricsError } = await supabase
        .from('sales_metrics')
        .select('user_id, calls_made, conversions')
        .in('user_id', userIds)
        .order('date', { ascending: false });

      if (metricsError) throw metricsError;

      // Aggregate metrics per user
      const metricsMap = new Map<string, { calls: number; conversions: number }>();
      (metrics || []).forEach((m) => {
        if (!m.user_id) return;
        const current = metricsMap.get(m.user_id) || { calls: 0, conversions: 0 };
        metricsMap.set(m.user_id, {
          calls: current.calls + (m.calls_made || 0),
          conversions: current.conversions + (m.conversions || 0),
        });
      });

      return (profiles || []).map((p) => {
        const userMetrics = metricsMap.get(p.user_id) || { calls: 0, conversions: 0 };
        return {
          name: p.name,
          score: p.score || 0,
          bonus: Number(p.total_bonus) || 0,
          calls: userMetrics.calls,
          conversions: userMetrics.conversions,
          user_id: p.user_id,
        } as TeamMemberPerformance;
      });
    },
    enabled: !!session?.user?.id && role === 'boss',
  });
}

// Fetch leaderboard data
export function useLeaderboard(limit: number = 5) {
  const { session } = useAuth();

  return useQuery({
    queryKey: ['leaderboard', limit],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('profiles')
        .select('user_id, name, score, total_bonus, rank')
        .order('score', { ascending: false })
        .limit(limit);

      if (error) throw error;

      return (data || []).map((p, index) => ({
        rank: index + 1,
        name: p.name,
        score: p.score || 0,
        bonus: Number(p.total_bonus) || 0,
        trend: 'stable' as const,
        isCurrentUser: p.user_id === session?.user?.id,
      }));
    },
    enabled: !!session?.user?.id,
  });
}

// Save daily sales metrics (with upsert to handle existing dates)
export function useSaveSalesMetric() {
  const queryClient = useQueryClient();
  const { session } = useAuth();

  return useMutation({
    mutationFn: async (metric: {
      leads_count?: number;
      conversions?: number;
      revenue?: number;
      win_rate?: number;
      calls_made?: number;
      score?: number;
      date?: string;
    }) => {
      if (!session?.user?.id) throw new Error('Not authenticated');

      const { data, error } = await supabase
        .from('sales_metrics')
        .upsert({
          user_id: session.user.id,
          date: metric.date || format(new Date(), 'yyyy-MM-dd'),
          leads_count: metric.leads_count || 0,
          conversions: metric.conversions || 0,
          revenue: metric.revenue || 0,
          win_rate: metric.win_rate || 0,
          calls_made: metric.calls_made || 0,
          score: metric.score || 0,
        }, { onConflict: 'user_id,date' })
        .select()
        .single();

      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales-metrics'] });
      queryClient.invalidateQueries({ queryKey: ['sales-metrics-range'] });
      queryClient.invalidateQueries({ queryKey: ['win-rate-history'] });
      queryClient.invalidateQueries({ queryKey: ['revenue-data'] });
      queryClient.invalidateQueries({ queryKey: ['team-performance'] });
      queryClient.invalidateQueries({ queryKey: ['leaderboard'] });
    },
  });
}

// Update user's profile score and bonus
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  const { session } = useAuth();

  return useMutation({
    mutationFn: async (updates: {
      score?: number;
      total_bonus?: number;
      rank?: number;
    }) => {
      if (!session?.user?.id) throw new Error('Not authenticated');

      const { data, error } = await supabase
        .from('profiles')
        .update(updates)
        .eq('user_id', session.user.id)
        .select()
        .single();

      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leaderboard'] });
      queryClient.invalidateQueries({ queryKey: ['team-performance'] });
    },
  });
}

// Generate mock data for demo purposes
export function useSeedDemoData() {
  const queryClient = useQueryClient();
  const { session } = useAuth();

  return useMutation({
    mutationFn: async () => {
      if (!session?.user?.id) throw new Error('Not authenticated');

      // Generate last 90 days of sample data
      const records = [];
      for (let i = 90; i >= 0; i--) {
        const date = format(subDays(new Date(), i), 'yyyy-MM-dd');
        records.push({
          user_id: session.user.id,
          date,
          leads_count: Math.floor(Math.random() * 10) + 1,
          conversions: Math.floor(Math.random() * 5),
          revenue: Math.floor(Math.random() * 50000) + 10000,
          win_rate: Math.floor(Math.random() * 30) + 10,
          calls_made: Math.floor(Math.random() * 20) + 5,
          score: Math.floor(Math.random() * 20) + 75,
        });
      }

      const { error } = await supabase
        .from('sales_metrics')
        .upsert(records, { onConflict: 'user_id,date', ignoreDuplicates: true });

      if (error) throw error;
      return { inserted: records.length };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales-metrics'] });
      queryClient.invalidateQueries({ queryKey: ['sales-metrics-range'] });
      queryClient.invalidateQueries({ queryKey: ['win-rate-history'] });
      queryClient.invalidateQueries({ queryKey: ['revenue-data'] });
    },
  });
}

// Export sales data as CSV
export function exportToCSV(data: SalesMetric[], filename: string = 'sales-report') {
  if (!data || data.length === 0) {
    throw new Error('No data to export');
  }

  const headers = ['日期', '线索数', '转化数', '营收', '赢率%', '通话数', '绩效分'];
  const rows = data.map(row => [
    row.date,
    row.leads_count || 0,
    row.conversions || 0,
    row.revenue || 0,
    row.win_rate || 0,
    row.calls_made || 0,
    row.score || 0,
  ]);

  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.join(','))
  ].join('\n');

  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `${filename}-${format(new Date(), 'yyyy-MM-dd')}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}
