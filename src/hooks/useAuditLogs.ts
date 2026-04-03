import { useQuery } from '@tanstack/react-query';
import { httpClient } from '@/lib/httpClient';

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

// ─── Table availability probe ──────────────────────────────
const _auditTableAvailable: boolean | null = true; // 默认可用

async function isAuditTableAvailable(): Promise<boolean> {
  return _auditTableAvailable !== false;
}

// ─── Hooks ──────────────────────────────────────────────────

/**
 * 查询审计日志
 */
export function useAuditLogs(filters: AuditFilters) {
  return useQuery({
    queryKey: ['audit-logs', filters],
    queryFn: async (): Promise<AuditLogEntry[]> => {
      if (!(await isAuditTableAvailable())) return [];

      const params = new URLSearchParams();
      if (filters.startDate) params.append('startDate', filters.startDate);
      if (filters.endDate) params.append('endDate', filters.endDate);
      if (filters.action && filters.action !== 'all') params.append('action', filters.action);
      if (filters.actor) params.append('actor', filters.actor);
      if (filters.status && filters.status !== 'all') params.append('status', filters.status);

      const response = await httpClient.get(`/api/system/audit-logs?${params}`);
      const result = response.data?.logs;
      return Array.isArray(result) ? result : [];
    },
    staleTime: 30_000,
    retry: false,
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
 * 可用的操作类型列表
 */
export function useAuditActions() {
  return useQuery({
    queryKey: ['audit-actions'],
    queryFn: async () => {
      if (!(await isAuditTableAvailable())) return [];
      const response = await httpClient.get('/api/system/audit-logs');
      const logs = Array.isArray(response.data?.logs) ? response.data.logs : [];
      return [...new Set(logs.map((l: AuditLogEntry) => l.action))];
    },
    staleTime: 60_000,
    retry: false,
  });
}
