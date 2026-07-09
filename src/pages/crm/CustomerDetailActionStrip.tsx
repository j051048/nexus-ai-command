import { MessageSquare } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { Customer, CustomerActivity } from '@/hooks/useCRM';
import { STAGES, ACTIVITY_NAMES } from './constants';

interface CustomerDetailActionStripProps {
  customer: Customer;
  health?: { risk_level?: string; health_score?: number } | null;
  timeline: CustomerActivity[];
  onAddActivity: () => void;
}

export function CustomerDetailActionStrip({
  customer,
  health,
  timeline,
  onAddActivity,
}: CustomerDetailActionStripProps) {
  const stageName = STAGES[customer.stage]?.name || customer.stage || '未标记';
  const lastActivity = timeline[0];
  const lastActivityLabel = lastActivity
    ? `${ACTIVITY_NAMES[lastActivity.activity_type] || lastActivity.activity_type} / ${new Date(lastActivity.created_at).toLocaleDateString('zh-CN')}`
    : '暂无跟进记录';
  const isRisky = health?.risk_level === 'at_risk' || health?.risk_level === 'churn_risk';
  const nextAction = isRisky
    ? '先补一次高质量跟进，确认需求、预算和下一步会议。'
    : lastActivity
      ? '延续最近沟通，更新下一步任务和成交概率。'
      : '先记录首次沟通，补齐联系人、需求和预算。';

  return (
    <section data-testid="customer-detail-next-action" className="mb-4 rounded-lg border bg-card px-3 py-2.5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{stageName}</Badge>
            {typeof health?.health_score === 'number' && (
              <Badge variant={isRisky ? 'destructive' : 'secondary'}>健康 {health.health_score}</Badge>
            )}
            <span className="text-xs text-muted-foreground">{lastActivityLabel}</span>
          </div>
          <p className="mt-2 line-clamp-1 text-sm font-medium">{nextAction}</p>
        </div>
        <Button size="sm" className="h-8 shrink-0" onClick={onAddActivity}>
          <MessageSquare className="mr-2 h-4 w-4" />
          记录跟进
        </Button>
      </div>
    </section>
  );
}
