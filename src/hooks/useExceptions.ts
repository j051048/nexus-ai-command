import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';

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
      const orgId = profile?.organization_id;

      // 1. 预算超支 (used > 90% of total)
      try {
        const { data: budgets } = await supabase.from('finance_budgets')
          .select('*')
          .eq('organization_id', orgId);

        for (const b of (budgets || [])) {
          const total = Number(b.total_amount || 0);
          const used = Number(b.used_amount || 0);
          if (total > 0 && used / total > 0.9) {
            const pct = Math.round((used / total) * 100);
            const period = (b as Record<string, unknown>).period ?? '';
            alerts.push({
              id: `budget-${b.id}`,
              type: 'budget_overrun',
              severity: pct >= 100 ? 'high' : 'medium',
              title: `预算超支: ${b.name}`,
              description: `${period} 预算已使用 ${pct}% (\u00A5${used.toLocaleString()} / \u00A5${total.toLocaleString()})`,
              entityId: b.id,
            });
          }
        }
      } catch {
        // table may not exist
      }

      // 2. 停滞商机 (30天+ 未更新)
      try {
        const thirtyDaysAgo = new Date(Date.now() - 30 * 86400000).toISOString();
        const { data: leads } = await supabase.from('sales_leads')
          .select('*')
          .eq('organization_id', orgId)
          .in('stage', ['lead', 'prospect', 'negotiation'])
          .lt('updated_at', thirtyDaysAgo)
          .limit(10);

        for (const l of (leads || [])) {
          const companyName = (l as Record<string, unknown>).company_name ?? (l as Record<string, unknown>).name ?? '未知';
          const stage = (l as Record<string, unknown>).stage ?? '';
          const updatedAt = (l as Record<string, unknown>).updated_at as string | undefined;
          if (!updatedAt) continue;
          const daysSince = Math.floor((Date.now() - new Date(updatedAt).getTime()) / 86400000);
          alerts.push({
            id: `lead-${l.id}`,
            type: 'stale_lead',
            severity: daysSince > 60 ? 'high' : 'medium',
            title: `商机停滞: ${companyName}`,
            description: `已 ${daysSince} 天未更新 (状态: ${stage})`,
            entityId: l.id,
          });
        }
      } catch {
        // table may not exist
      }

      // 3. 合同即将到期 (30天内)
      try {
        const today = new Date().toISOString().slice(0, 10);
        const thirtyDaysLater = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10);
        const { data: contracts } = await supabase.from('contracts')
          .select('id, title, end_date, status')
          .eq('organization_id', orgId)
          .eq('status', 'active')
          .gte('end_date', today)
          .lte('end_date', thirtyDaysLater)
          .limit(10);

        for (const c of (contracts || [])) {
          const daysLeft = Math.floor((new Date(c.end_date).getTime() - Date.now()) / 86400000);
          alerts.push({
            id: `contract-${c.id}`,
            type: 'contract_expiry',
            severity: daysLeft <= 7 ? 'high' : daysLeft <= 14 ? 'medium' : 'low',
            title: `合同到期: ${c.title || '未命名合同'}`,
            description: `将在 ${daysLeft} 天后到期 (${c.end_date})`,
            entityId: c.id,
          });
        }
      } catch {
        // table may not exist
      }

      // Sort by severity
      const severityOrder = { high: 0, medium: 1, low: 2 };
      alerts.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);

      return alerts;
    },
    enabled: !!profile?.organization_id,
    staleTime: 60_000,
  });
}
