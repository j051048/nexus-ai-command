import { Loader2 } from 'lucide-react';

import { Progress } from '@/components/ui/progress';
import { useOperationalAnalytics } from '@/hooks/useSuperAdminConsole';

const PLAN_NAMES: Record<string, string> = { free: '未开通', starter: '团队版', professional: '专业版', enterprise: '企业版' };

export function AdminAnalyticsPanel() {
  const { data, isLoading } = useOperationalAnalytics();
  if (isLoading || !data) return <div className="flex min-h-64 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin" /></div>;
  const planTotal = Object.values(data.plan_distribution).reduce((sum, value) => sum + value, 0) || 1;
  const requestTotal = Object.values(data.requests_30d).reduce((sum, value) => sum + value, 0);
  return (
    <section className="space-y-8">
      <div><h3 className="font-semibold">运营分析</h3><p className="mt-1 text-sm text-muted-foreground">围绕处理效率、续期风险、商业回款与 AI 成本做决策。</p></div>
      <div className="grid border-y sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="平均审核时长" value={`${data.average_review_hours} 小时`} />
        <Metric label="30 天申请" value={requestTotal.toLocaleString()} bordered />
        <Metric label="待回款" value={`¥${(data.commercial.outstanding_cents / 100).toLocaleString()}`} bordered />
        <Metric label="30 天内到期" value={String(data.expiring['30_days'])} bordered />
      </div>
      <div className="grid gap-10 lg:grid-cols-2">
        <section><h4 className="text-sm font-medium">套餐分布</h4><div className="mt-4 space-y-4">{Object.entries(data.plan_distribution).map(([plan, count]) => <div key={plan}><div className="mb-1.5 flex justify-between text-sm"><span>{PLAN_NAMES[plan] ?? plan}</span><span className="tabular-nums text-muted-foreground">{count}</span></div><Progress value={(count / planTotal) * 100} className="h-1.5" /></div>)}</div></section>
        <section><h4 className="text-sm font-medium">到期风险</h4><div className="mt-4 divide-y border-y"><RiskRow label="未来 7 天" value={data.expiring['7_days']} tone="danger" /><RiskRow label="未来 30 天" value={data.expiring['30_days']} /><RiskRow label="未来 90 天" value={data.expiring['90_days']} /></div></section>
      </div>
      <section><h4 className="text-sm font-medium">AI 成本最高的企业</h4><div className="mt-3 divide-y border-y">{data.top_cost_organizations.length === 0 && <p className="py-8 text-center text-sm text-muted-foreground">暂无成本数据</p>}{data.top_cost_organizations.map((item, index) => <div key={item.org_id} className="grid gap-3 py-3 sm:grid-cols-[40px_1fr_150px_150px] sm:items-center"><span className="text-xs text-muted-foreground">{String(index + 1).padStart(2, '0')}</span><p className="text-sm font-medium">{item.organization_name}</p><p className="text-sm tabular-nums">${item.cost_usd.toFixed(4)}</p><p className="text-xs tabular-nums text-muted-foreground">{item.requests.toLocaleString()} 次请求</p></div>)}</div></section>
    </section>
  );
}

function Metric({ label, value, bordered }: { label: string; value: string; bordered?: boolean }) {
  return <div className={`py-4 sm:px-5 ${bordered ? 'sm:border-l' : ''}`}><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-xl font-semibold tabular-nums">{value}</p></div>;
}

function RiskRow({ label, value, tone }: { label: string; value: number; tone?: 'danger' }) {
  return <div className="flex items-center justify-between py-4"><span className="text-sm">{label}</span><span className={`text-lg font-semibold tabular-nums ${tone === 'danger' && value ? 'text-destructive' : ''}`}>{value}</span></div>;
}
