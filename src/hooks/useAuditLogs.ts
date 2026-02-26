import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';

// ─── 类型定义 ──────────────────────────────────────────────

export interface AuditLogEntry {
  id: string;
  action: string;
  actor: string;
  target?: string;
  details?: string;
  status: 'success' | 'failure' | 'warning';
  ip_address?: string;
  user_agent?: string;
  created_at: string;
}

export interface AuditFilters {
  startDate?: string;
  endDate?: string;
  action?: string;
  actor?: string;
  status?: string;
}

export interface AuditStats {
  totalOps: number;
  failedOps: number;
  securityAlerts: number;
  hourlyDistribution: { hour: number; count: number }[];
}

// ─── 统计计算 ──────────────────────────────────────────────

function calculateStats(logs: AuditLogEntry[]): AuditStats {
  const hourlyMap = new Map<number, number>();
  for (let h = 0; h < 24; h++) hourlyMap.set(h, 0);

  logs.forEach((log) => {
    const hour = new Date(log.created_at).getHours();
    hourlyMap.set(hour, (hourlyMap.get(hour) || 0) + 1);
  });

  return {
    totalOps: logs.length,
    failedOps: logs.filter((l) => l.status === 'failure').length,
    securityAlerts: logs.filter((l) => l.status === 'warning').length,
    hourlyDistribution: Array.from(hourlyMap.entries()).map(([hour, count]) => ({ hour, count })),
  };
}

// ─── Hooks ──────────────────────────────────────────────────

/**
 * 查询审计日志
 * 从 Supabase audit_logs 表获取真实数据，查询失败时抛出错误
 */
export function useAuditLogs(filters: AuditFilters) {
  return useQuery({
    queryKey: ['audit-logs', filters],
    queryFn: async (): Promise<AuditLogEntry[]> => {
      let query = supabase.from('audit_logs').select('*').order('created_at', { ascending: false }).limit(200);

      if (filters.startDate) {
        query = query.gte('created_at', filters.startDate);
      }
      if (filters.endDate) {
        query = query.lte('created_at', filters.endDate + 'T23:59:59');
      }
      if (filters.action && filters.action !== 'all') {
        query = query.eq('action', filters.action);
      }
      if (filters.actor) {
        query = query.ilike('actor', `%${filters.actor}%`);
      }
      if (filters.status && filters.status !== 'all') {
        query = query.eq('status', filters.status);
      }

      const { data, error } = await query;
      if (error) throw error;
      return (data as AuditLogEntry[]) || [];
    },
    staleTime: 30_000,
  });
}

/**
 * 审计统计数据 — 基于真实日志数据计算
 */
export function useAuditStats(filters: AuditFilters) {
  const logsQuery = useAuditLogs(filters);

  return useQuery({
    queryKey: ['audit-stats', filters],
    queryFn: async (): Promise<AuditStats> => {
      const logs = logsQuery.data || [];
      return calculateStats(logs);
    },
    enabled: !!logsQuery.data,
    staleTime: 30_000,
  });
}

/**
 * 可用的操作类型列表（从真实数据中提取去重）
 */
export function useAuditActions() {
  return useQuery({
    queryKey: ['audit-actions'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('audit_logs')
        .select('action')
        .order('action');
      if (error) throw error;
      const actions: string[] = [...new Set((data as { action: string }[]).map((d) => d.action))];
      return actions;
    },
    staleTime: 60_000,
  });
}
