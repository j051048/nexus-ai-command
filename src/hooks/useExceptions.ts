import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthContext';
import { httpClient } from '@/lib/httpClient';

export interface ExceptionAlert {
  id: string;
  type: 'budget_overrun' | 'stale_lead' | 'contract_expiry';
  severity: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  entityId?: string;
}

export function useExceptions() {
  const { profile } = useAuth();

  return useQuery({
    queryKey: ['exceptions', profile?.organization_id],
    queryFn: async () => {
      const alerts: ExceptionAlert[] = [];

      // 1. 预算超支
      try {
        const response = await httpClient.get('/api/finance/budgets');
        const budgets = Array.isArray(response.data?.budgets) ? response.data.budgets : [];
        for (const b of budgets) {
          const total = Number(b.total_amount || 0);
          const used = Number(b.used_amount || 0);
          if (total > 0 && used / total > 0.9) {
            const pct = Math.round((used / total) * 100);
            alerts.push({
              id: `budget-${b.id}`,
              type: 'budget_overrun',
              severity: pct >= 100 ? 'high' : 'medium',
              title: `预算超支: ${b.name}`,
              description: `预算已使用 ${pct}% (¥${used.toLocaleString()} / ¥${total.toLocaleString()})`,
              entityId: b.id,
            });
          }
        }
      } catch { /* non-critical */ }

      // 2. 停滞商机
      try {
        const response = await httpClient.get('/api/sales-leads');
        const leads = Array.isArray(response.data?.leads) ? response.data.leads : [];
        for (const l of leads) {
          const updatedAt = l.updated_at;
          if (!updatedAt) continue;
          const daysSince = Math.floor((Date.now() - new Date(updatedAt).getTime()) / 86400000);
          if (daysSince > 30) {
            alerts.push({
              id: `lead-${l.id}`,
              type: 'stale_lead',
              severity: daysSince > 60 ? 'high' : 'medium',
              title: `商机停滞: ${l.customer_name || '未知'}`,
              description: `已 ${daysSince} 天未更新`,
              entityId: l.id,
            });
          }
        }
      } catch { /* non-critical */ }

      // 3. 合同即将到期
      try {
        const response = await httpClient.get('/api/contracts');
        const contracts = Array.isArray(response.data?.contracts) ? response.data.contracts : [];
        for (const c of contracts) {
          if (c.status === 'active' && c.end_date) {
            const daysLeft = Math.floor((new Date(c.end_date).getTime() - Date.now()) / 86400000);
            if (daysLeft <= 30 && daysLeft >= 0) {
              alerts.push({
                id: `contract-${c.id}`,
                type: 'contract_expiry',
                severity: daysLeft <= 7 ? 'high' : daysLeft <= 14 ? 'medium' : 'low',
                title: `合同到期: ${c.title || '未命名合同'}`,
                description: `将在 ${daysLeft} 天后到期`,
                entityId: c.id,
              });
            }
          }
        }
      } catch { /* non-critical */ }

      const severityOrder = { high: 0, medium: 1, low: 2 };
      alerts.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);
      return alerts;
    },
    enabled: !!profile?.organization_id,
    staleTime: 60_000,
  });
}
