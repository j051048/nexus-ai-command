import { useMemo, useState } from 'react';
import { AlertTriangle, Building2, Loader2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { type OperationalException, useOperationalExceptions } from '@/hooks/useSuperAdminConsole';

const SEVERITY: Record<string, { label: string; className: string }> = {
  critical: { label: '严重', className: 'border-destructive/30 bg-destructive/5 text-destructive' },
  high: { label: '高', className: 'border-amber-500/30 bg-amber-500/5 text-amber-700' },
  medium: { label: '中', className: 'border-border bg-muted/50 text-muted-foreground' },
  low: { label: '低', className: 'border-border text-muted-foreground' },
};

export function AdminExceptionsPanel({ onOpenOrganization }: { onOpenOrganization: (orgId: string) => void }) {
  const { data = [], isLoading } = useOperationalExceptions();
  const [filter, setFilter] = useState<'all' | OperationalException['severity']>('all');
  const visible = useMemo(() => filter === 'all' ? data : data.filter((item) => item.severity === filter), [data, filter]);

  if (isLoading) return <div className="flex min-h-64 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin" /></div>;
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h3 className="font-semibold">运营异常</h3><p className="mt-1 text-sm text-muted-foreground">只展示需要平台人员采取行动的问题。</p></div>
        <div className="flex items-center gap-1">
          {(['all', 'critical', 'high', 'medium'] as const).map((value) => (
            <Button key={value} variant={filter === value ? 'secondary' : 'ghost'} size="sm" onClick={() => setFilter(value)}>
              {value === 'all' ? `全部 ${data.length}` : SEVERITY[value].label}
            </Button>
          ))}
        </div>
      </div>
      {visible.length === 0 ? (
        <div className="flex min-h-56 flex-col items-center justify-center border-y text-center"><AlertTriangle className="h-5 w-5 text-muted-foreground" /><p className="mt-3 font-medium">当前没有运营异常</p></div>
      ) : (
        <div className="divide-y border-y">
          {visible.map((item) => (
            <div key={item.id} className="grid gap-3 py-4 lg:grid-cols-[90px_1fr_220px_auto] lg:items-center">
              <Badge variant="outline" className={`w-fit ${SEVERITY[item.severity]?.className}`}>{SEVERITY[item.severity]?.label ?? item.severity}</Badge>
              <div><p className="font-medium">{item.title}</p><p className="mt-1 text-sm text-muted-foreground">{item.detail}</p></div>
              <div className="text-sm"><p className="flex items-center gap-1.5"><Building2 className="h-3.5 w-3.5 text-muted-foreground" />{item.organization_name}</p><p className="mt-1 text-xs text-muted-foreground">建议：{item.recommended_action}</p></div>
              <Button variant="outline" size="sm" onClick={() => onOpenOrganization(item.org_id)}>处理</Button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
