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

// ─── Mock 数据生成 ──────────────────────────────────────────

const ACTIONS = [
  '用户登录', '用户登出', '创建审批', '审批通过', '审批拒绝',
  '修改权限', '删除记录', '导出数据', '修改设置', '密码重置',
  '创建项目', '修改表单', 'API调用', '文件上传', '配置变更',
];

const ACTORS = ['张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十', '系统'];

const STATUSES: AuditLogEntry['status'][] = ['success', 'success', 'success', 'success', 'failure', 'warning'];

function generateMockLogs(filters: AuditFilters): AuditLogEntry[] {
  const logs: AuditLogEntry[] = [];
  const now = new Date();

  for (let i = 0; i < 50; i++) {
    const date = new Date(now.getTime() - Math.random() * 7 * 24 * 60 * 60 * 1000);
    const action = ACTIONS[Math.floor(Math.random() * ACTIONS.length)];
    const actor = ACTORS[Math.floor(Math.random() * ACTORS.length)];
    const status = STATUSES[Math.floor(Math.random() * STATUSES.length)];

    // 应用过滤
    if (filters.action && filters.action !== 'all' && action !== filters.action) continue;
    if (filters.actor && !actor.includes(filters.actor)) continue;
    if (filters.status && filters.status !== 'all' && status !== filters.status) continue;
    if (filters.startDate && date < new Date(filters.startDate)) continue;
    if (filters.endDate && date > new Date(filters.endDate + 'T23:59:59')) continue;

    logs.push({
      id: `audit-${i}-${Date.now()}`,
      action,
      actor,
      target: `资源-${Math.floor(Math.random() * 100)}`,
      details: `${actor} 执行了 ${action} 操作`,
      status,
      ip_address: `192.168.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
      created_at: date.toISOString(),
    });
  }

  return logs.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}

function generateMockStats(logs: AuditLogEntry[]): AuditStats {
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
 * 优先尝试 supabase audit_logs 表，fallback 到 mock 数据
 */
export function useAuditLogs(filters: AuditFilters) {
  return useQuery({
    queryKey: ['audit-logs', filters],
    queryFn: async (): Promise<AuditLogEntry[]> => {
      try {
        let query = (supabase as any).from('audit_logs').select('*').order('created_at', { ascending: false }).limit(200);

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
      } catch {
        // supabase 表不存在或查询失败，使用 mock 数据
        return generateMockLogs(filters);
      }
    },
    staleTime: 30_000,
  });
}

/**
 * 审计统计数据
 */
export function useAuditStats(filters: AuditFilters) {
  const logsQuery = useAuditLogs(filters);

  return useQuery({
    queryKey: ['audit-stats', filters],
    queryFn: async (): Promise<AuditStats> => {
      const logs = logsQuery.data || [];
      return generateMockStats(logs);
    },
    enabled: !!logsQuery.data,
    staleTime: 30_000,
  });
}

/**
 * 可用的操作类型列表（用于筛选下拉）
 */
export function useAuditActions() {
  return useQuery({
    queryKey: ['audit-actions'],
    queryFn: async () => {
      return ACTIONS;
    },
    staleTime: Infinity,
  });
}
