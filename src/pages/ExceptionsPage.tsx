import React from 'react';
import { BossApprovalView } from '@/components/approval/sections/BossApprovalView';
import { AlertTriangle, DollarSign, Users, FileText, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useExceptions, type ExceptionAlert } from '@/hooks/useExceptions';

const typeConfig: Record<string, { icon: React.ElementType; color: string }> = {
  budget_overrun: { icon: DollarSign, color: 'text-red-500' },
  stale_lead: { icon: Users, color: 'text-orange-500' },
  contract_expiry: { icon: FileText, color: 'text-yellow-500' },
};

const severityConfig: Record<string, { label: string; color: string }> = {
  high: { label: '高', color: 'bg-red-500/10 text-red-600 border-red-200' },
  medium: { label: '中', color: 'bg-yellow-500/10 text-yellow-600 border-yellow-200' },
  low: { label: '低', color: 'bg-blue-500/10 text-blue-600 border-blue-200' },
};

export default function ExceptionsPage() {
  const { data: alerts = [], isLoading } = useExceptions();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-warning/20 flex items-center justify-center">
          <AlertTriangle className="w-6 h-6 text-warning" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">异常待办中心</h1>
          <p className="text-muted-foreground mt-1">
            集中处理超出阈值、合规风险及紧急审批事项
          </p>
        </div>
      </div>

      <div className="bg-warning/5 border border-warning/20 rounded-lg p-4 mb-6">
        <h3 className="text-warning font-semibold flex items-center gap-2 mb-2">
          <AlertTriangle className="w-4 h-4" />
          系统检测到以下异常
          {!isLoading && <Badge variant="outline" className="ml-2">{alerts.length} 项</Badge>}
        </h3>

        {isLoading ? (
          <div className="flex items-center gap-2 py-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm text-muted-foreground">检测中...</span>
          </div>
        ) : alerts.length === 0 ? (
          <p className="text-sm text-muted-foreground py-2">当前无异常事项</p>
        ) : (
          <div className="space-y-2">
            {alerts.map((alert: ExceptionAlert) => {
              const typeCfg = typeConfig[alert.type] || typeConfig.budget_overrun;
              const sevCfg = severityConfig[alert.severity] || severityConfig.medium;
              const Icon = typeCfg.icon;
              return (
                <div key={alert.id} className="flex items-center gap-3 p-2 rounded-lg border bg-background">
                  <Icon className={cn('w-4 h-4 shrink-0', typeCfg.color)} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{alert.title}</p>
                    <p className="text-xs text-muted-foreground truncate">{alert.description}</p>
                  </div>
                  <Badge className={cn('text-xs shrink-0', sevCfg.color)}>{sevCfg.label}</Badge>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <BossApprovalView />
    </div>
  );
}
