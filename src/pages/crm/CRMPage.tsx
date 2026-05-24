import React, { useState, useMemo } from 'react';
import { useDebounce } from '@/hooks/useDebounce';
import { NoDataYet, NoSearchResults } from '@/components/common/EmptyState';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LoadingState } from '@/components/common/LoadingState';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import {
  Users,
  Plus,
  ArrowRightLeft,
  DollarSign,
  TrendingUp,
  Trash2,
  Loader2,
  Sparkles,
  AlertTriangle,
} from 'lucide-react';
import {
  useCustomers,
  useCustomerStats,
  useDeleteCustomer,
} from '@/hooks/useCRM';
import type { Customer } from '@/hooks/useCRM';
import CustomerFilters from './CustomerFilters';
import CustomerKanban from './CustomerKanban';
import CustomerTable from './CustomerTable';
import CustomerDetailSheet from './CustomerDetailSheet';
import CustomerFormDialog from './CustomerFormDialog';
import { EditCustomerDialog } from './CustomerDetailSheet';
import { iconColors, iconBackgrounds, spacing, typography } from '@/lib/design-tokens';
import { AIQuickActions } from '@/components/ai/AIQuickActions';
import { useRegisterPageContext } from '@/hooks/usePageContext';

function daysSince(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return Math.floor((Date.now() - date.getTime()) / 86_400_000);
}

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

function CRMAIInsightLayer({
  customers,
  stats,
}: {
  customers: Customer[];
  stats: Record<string, unknown> | undefined;
}) {
  const staleCustomers = customers
    .map((customer) => ({ customer, staleDays: daysSince(customer.updated_at) ?? 0 }))
    .filter((item) => item.staleDays >= 30)
    .sort((a, b) => b.staleDays - a.staleDays);
  const highValueOpen = customers.filter(
    (customer) =>
      Number(customer.estimated_value ?? 0) >= 50000 &&
      !['customer', 'closed', 'lost'].includes(String(customer.stage)),
  );
  const topRisk = staleCustomers[0]?.customer;
  const topRiskDays = staleCustomers[0]?.staleDays ?? 0;
  const evidenceCards = [
    {
      label: '长期未跟进',
      value: `${staleCustomers.length} 个`,
      hint: topRisk ? `${topRisk.name} 已 ${topRiskDays} 天未更新` : '暂无 30 天以上停滞客户',
    },
    {
      label: '高价值机会',
      value: `${highValueOpen.length} 个`,
      hint: '预计金额超过 ¥50,000 且尚未关闭',
    },
    {
      label: 'AI 风险依据',
      value: topRisk ? '需复核' : '稳定',
      hint: '综合阶段、金额、最近更新时间生成',
    },
  ];

  return (
    <section className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold">AI 客户摘要</h2>
              {staleCustomers.length > 0 && (
                <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-600">
                  {staleCustomers.length} 个客户需跟进
                </span>
              )}
            </div>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              当前客户池共 {Number(stats?.total_customers ?? customers.length)} 个客户，
              {highValueOpen.length} 个高价值机会仍在推进中
              {topRisk ? `，${topRisk.name} 已较久未更新，建议优先确认下一步。` : '，暂无明显长期停滞客户。'}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            onClick={() =>
              triggerAI('请基于当前 CRM 客户列表，生成高价值机会和风险客户的跟进优先级。')
            }
          >
            <Sparkles className="mr-2 h-4 w-4" />
            生成跟进优先级
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              triggerAI('请帮我写一份今天的 CRM 销售晨会摘要，包含新增、机会、风险和下一步动作。')
            }
          >
            晨会摘要
          </Button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {evidenceCards.map((card) => (
          <div key={card.label} className="rounded-lg border bg-background/60 p-3">
            <div className="text-xs text-muted-foreground">{card.label}</div>
            <div className="mt-1 text-lg font-semibold">{card.value}</div>
            <div className="mt-1 text-xs leading-5 text-muted-foreground">{card.hint}</div>
          </div>
        ))}
      </div>

      {topRisk && (
        <div className="mt-4 rounded-lg border border-amber-500/25 bg-amber-500/10 p-3 text-sm">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
            <p className="text-amber-700 dark:text-amber-300">
              建议今天先处理 {topRisk.name}：该客户处于 {topRisk.stage || '未标记'} 阶段，
              预计金额 ¥{Number(topRisk.estimated_value ?? 0).toLocaleString()}。
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

function StatsBar() {
  const { data: stats, isLoading } = useCustomerStats();

  if (isLoading) {
    return <LoadingState type="skeleton" rows={1} className="h-24" />;
  }

  const items = [
    { label: '客户总数', value: stats?.total_customers ?? 0, icon: Users, color: iconColors.blue, bg: iconBackgrounds.blue },
    { label: '本月新增', value: stats?.new_this_month ?? 0, icon: Plus, color: iconColors.green, bg: iconBackgrounds.green },
    { label: '转化率', value: `${stats?.conversion_rate ?? 0}%`, icon: ArrowRightLeft, color: iconColors.orange, bg: iconBackgrounds.orange },
    { label: '预估总额', value: `¥${Number(stats?.total_estimated_value ?? 0).toLocaleString()}`, icon: DollarSign, color: iconColors.purple, bg: iconBackgrounds.purple },
    { label: '流失', value: stats?.churned ?? 0, icon: TrendingUp, color: iconColors.red, bg: iconBackgrounds.red },
  ];

  return (
    <div className={cn('grid grid-cols-2 md:grid-cols-5', spacing.sm)}>
      {items.map(item => (
        <Card key={item.label} variant="elevated">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-3">
              <span className={cn(typography.xs)}>{item.label}</span>
              <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', item.bg)}>
                <item.icon className={cn('w-5 h-5', item.color)} />
              </div>
            </div>
            <p className={cn(typography.h2, item.color)}>{item.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function CRMPage() {
  const [viewMode, setViewMode] = useState<'kanban' | 'list'>('kanban');
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebounce(searchQuery, 300);
  const [stageFilter, setStageFilter] = useState('all');
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editFromList, setEditFromList] = useState<Customer | null>(null);
  const [deleteFromList, setDeleteFromList] = useState<Customer | null>(null);
  const deleteMutation = useDeleteCustomer();
  const statsQuery = useCustomerStats();

  // Register page context for AI panel
  useRegisterPageContext(
    selectedCustomer
      ? { type: 'customer', id: selectedCustomer.id, name: selectedCustomer.name }
      : { type: 'crm' }
  );

  const filters = useMemo(() => {
    const f: Record<string, string> = {};
    if (stageFilter !== 'all') f.stage = stageFilter;
    if (debouncedSearch) f.search = debouncedSearch;
    return f;
  }, [stageFilter, debouncedSearch]);

  const {
    data: customersData,
    isLoading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useCustomers(filters);
  const customers = useMemo(
    () => (customersData?.pages ?? []).flatMap((p) => p.data),
    [customersData],
  ) as Customer[];

  const handleSelectCustomer = (customer: Customer) => {
    setSelectedCustomer(customer);
    setDetailOpen(true);
  };

  return (
    <div className={cn('space-y-6')}>
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className={cn(typography.h1)}>客户管理</h1>
          <p className={cn(typography.small, 'text-muted-foreground mt-1')}>管理客户关系，跟踪销售漏斗</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            className="gap-2"
            onClick={() =>
              triggerAI('请帮我快速记录一次客户拜访，提取客户名称、联系人、需求、异议、预算、下一步动作和跟进时间。')
            }
          >
            <Sparkles className="w-4 h-4" />
            记录拜访
          </Button>
          <Button className="gap-2" onClick={() => setCreateOpen(true)}>
            <Plus className="w-4 h-4" />
            新建客户
          </Button>
        </div>
      </div>

      <StatsBar />

      <AIQuickActions pageType="crm" />

      <CRMAIInsightLayer customers={customers} stats={statsQuery.data} />

      <CustomerFilters
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        stageFilter={stageFilter}
        onStageFilterChange={setStageFilter}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        customers={customers as unknown as Record<string, unknown>[]}
        onReset={() => {
          setSearchQuery('');
          setStageFilter('all');
        }}
      />

      {isLoading ? (
        <LoadingState type="skeleton" rows={4} message="加载客户数据..." />
      ) : customers.length === 0 ? (
        debouncedSearch ? (
          <NoSearchResults query={searchQuery} onClear={() => setSearchQuery('')} />
        ) : (
          <NoDataYet resourceName="客户" onAdd={() => setCreateOpen(true)} />
        )
      ) : viewMode === 'kanban' ? (
        <CustomerKanban customers={customers} onSelect={handleSelectCustomer} />
      ) : (
        <CustomerTable
          customers={customers}
          onSelect={handleSelectCustomer}
          onEdit={(c) => setEditFromList(c)}
          onDelete={(c) => setDeleteFromList(c)}
        />
      )}

      {hasNextPage && (
        <div className="flex justify-center">
          <Button variant="outline" disabled={isFetchingNextPage} onClick={() => fetchNextPage()}>
            {isFetchingNextPage ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />加载中...</> : '加载更多'}
          </Button>
        </div>
      )}

      <CustomerDetailSheet
        customer={selectedCustomer}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
      />

      <CustomerFormDialog open={createOpen} onClose={() => setCreateOpen(false)} />

      {editFromList && (
        <EditCustomerDialog customer={editFromList} open={!!editFromList} onClose={() => setEditFromList(null)} />
      )}

      <Dialog open={!!deleteFromList} onOpenChange={() => setDeleteFromList(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="w-5 h-5" />
              确认删除客户
            </DialogTitle>
            <DialogDescription>
              您即将删除客户 <strong>{deleteFromList?.name}</strong>。此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteFromList(null)}>取消</Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={async () => {
                if (!deleteFromList) return;
                try {
                  await deleteMutation.mutateAsync(deleteFromList.id);
                  setDeleteFromList(null);
                } catch { /* hook handles toast */ }
              }}
            >
              {deleteMutation.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              确认删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default CRMPage;
