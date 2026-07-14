import { useMemo, useState } from 'react';
import { CircleDollarSign, Loader2, Search } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { type AdminOrganization, useCommercialRecords } from '@/hooks/useSuperAdminConsole';

const PAYMENT_NAMES: Record<string, string> = {
  pending: '待回款',
  partial: '部分回款',
  paid: '已回款',
  overdue: '已逾期',
  waived: '已豁免',
  refunded: '已退款',
};

export function AdminCommercialLedger({
  organizations,
  onOpenOrganization,
}: {
  organizations: AdminOrganization[];
  onOpenOrganization: (orgId: string) => void;
}) {
  const { data = [], isLoading } = useCommercialRecords();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const orgNames = useMemo(() => Object.fromEntries(organizations.map((item) => [item.id, item.name])), [organizations]);
  const visible = useMemo(() => data.filter((item) => {
    const matchesStatus = status === 'all' || item.payment_status === status;
    const term = search.trim().toLowerCase();
    return matchesStatus && (!term || item.order_number.toLowerCase().includes(term) || (orgNames[item.org_id] ?? '').toLowerCase().includes(term));
  }), [data, orgNames, search, status]);

  const totals = useMemo(() => ({
    collected: data.filter((item) => item.payment_status === 'paid').reduce((sum, item) => sum + item.amount_cents - item.discount_cents, 0),
    outstanding: data.filter((item) => ['pending', 'partial', 'overdue'].includes(item.payment_status)).reduce((sum, item) => sum + item.amount_cents - item.discount_cents, 0),
    overdue: data.filter((item) => item.payment_status === 'overdue').length,
  }), [data]);

  if (isLoading) return <div className="flex min-h-64 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin" /></div>;
  return (
    <section className="space-y-5">
      <div><h3 className="font-semibold">商业台账</h3><p className="mt-1 text-sm text-muted-foreground">合同、回款和发票是开通依据，不直接替代会员状态。</p></div>
      <div className="grid border-y sm:grid-cols-3">
        <Metric label="累计回款" value={`¥${(totals.collected / 100).toLocaleString()}`} />
        <Metric label="待回款" value={`¥${(totals.outstanding / 100).toLocaleString()}`} bordered />
        <Metric label="逾期订单" value={String(totals.overdue)} bordered tone={totals.overdue ? 'danger' : undefined} />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><Input className="w-72 pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索企业或订单" /></div>
        <div className="flex gap-1">{['all', 'pending', 'paid', 'overdue'].map((value) => <Button key={value} variant={status === value ? 'secondary' : 'ghost'} size="sm" onClick={() => setStatus(value)}>{value === 'all' ? '全部' : PAYMENT_NAMES[value]}</Button>)}</div>
      </div>
      {visible.length === 0 ? (
        <div className="flex min-h-52 flex-col items-center justify-center border-y"><CircleDollarSign className="h-5 w-5 text-muted-foreground" /><p className="mt-3 font-medium">暂无匹配的商业记录</p></div>
      ) : (
        <div className="divide-y border-y">
          {visible.map((item) => (
            <div key={item.id} className="grid gap-3 py-4 lg:grid-cols-[1fr_180px_150px_130px_auto] lg:items-center">
              <div><p className="font-medium">{item.order_number}</p><p className="mt-1 text-xs text-muted-foreground">{orgNames[item.org_id] ?? item.org_id} · 合同 {item.contract_number || '未关联'}</p></div>
              <p className="font-medium tabular-nums">¥{((item.amount_cents - item.discount_cents) / 100).toLocaleString()}</p>
              <Badge variant="outline" className="w-fit">{PAYMENT_NAMES[item.payment_status] ?? item.payment_status}</Badge>
              <p className="text-xs text-muted-foreground">{item.due_at ? new Date(item.due_at).toLocaleDateString('zh-CN') : '未设应收日'}</p>
              <Button variant="ghost" size="sm" onClick={() => onOpenOrganization(item.org_id)}>查看企业</Button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function Metric({ label, value, bordered, tone }: { label: string; value: string; bordered?: boolean; tone?: 'danger' }) {
  return <div className={`py-4 sm:px-5 ${bordered ? 'sm:border-l' : ''}`}><p className="text-xs text-muted-foreground">{label}</p><p className={`mt-1 text-xl font-semibold tabular-nums ${tone === 'danger' ? 'text-destructive' : ''}`}>{value}</p></div>;
}
