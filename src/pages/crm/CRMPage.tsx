import { useMemo, useState } from 'react';
import { ArrowRightLeft, DollarSign, Loader2, Plus, Sparkles, Trash2, TrendingUp, Users } from 'lucide-react';
import { toast } from 'sonner';
import { NoDataYet, NoSearchResults } from '@/components/common/EmptyState';
import { LoadingState } from '@/components/common/LoadingState';
import { AIQuickActions } from '@/components/ai/AIQuickActions';
import { AIInsightPanel } from '@/components/ai/AIInsightPanel';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useDebounce } from '@/hooks/useDebounce';
import { useRegisterPageContext } from '@/hooks/usePageContext';
import { useCustomers, useCustomerStats, useDeleteCustomer, type Customer } from '@/hooks/useCRM';
import { cn } from '@/lib/utils';
import { iconBackgrounds, iconColors, spacing, typography } from '@/lib/design-tokens';
import CustomerDetailSheet, { EditCustomerDialog } from './CustomerDetailSheet';
import CustomerFilters from './CustomerFilters';
import CustomerFormDialog from './CustomerFormDialog';
import CustomerKanban from './CustomerKanban';
import CustomerTable from './CustomerTable';

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
  const trustLevel = staleCustomers.length > 3 ? 'medium' : 'high';
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
    <AIInsightPanel
      title="AI 客户摘要"
      icon={Sparkles}
      trustLevel={trustLevel}
      score={trustLevel === 'high' ? 88 : 74}
      summary={
        <>
          当前客户池共 {Number(stats?.total_customers ?? customers.length)} 个客户，
          {highValueOpen.length} 个高价值机会仍在推进中
          {topRisk ? `，${topRisk.name} 已较久未更新，建议优先确认下一步。` : '，暂无明显长期停滞客户。'}
        </>
      }
      context={['CRM', '客户健康分', '跟进节奏']}
      evidence={evidenceCards.map((card) => ({
        label: card.label,
        value: (
          <>
            <span className="text-lg font-semibold">{card.value}</span>
            <span className="mt-1 block text-xs font-normal leading-5 text-muted-foreground">{card.hint}</span>
          </>
        ),
      }))}
      risks={
        topRisk
          ? [
              `${topRisk.name} ${topRiskDays} 天未跟进`,
              `阶段：${topRisk.stage || '未标记'}`,
              `预计金额 ¥${Number(topRisk.estimated_value ?? 0).toLocaleString()}`,
            ]
          : []
      }
      actions={[
        {
          label: '生成跟进优先级',
          variant: 'default',
          prompt: '请基于当前 CRM 客户列表，生成高价值机会和风险客户的跟进优先级。',
        },
        {
          label: '晨会摘要',
          prompt: '请帮我写一份今天的 CRM 销售晨会摘要，包含新增、机会、风险和下一步动作。',
        },
      ]}
    />
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
    { label: '预计金额', value: `¥${Number(stats?.total_estimated_value ?? 0).toLocaleString()}`, icon: DollarSign, color: iconColors.purple, bg: iconBackgrounds.purple },
    { label: '流失', value: stats?.churned ?? 0, icon: TrendingUp, color: iconColors.red, bg: iconBackgrounds.red },
  ];

  return (
    <div className={cn('grid grid-cols-2 md:grid-cols-5', spacing.sm)}>
      {items.map((item) => (
        <Card key={item.label} variant="elevated">
          <CardContent className="p-6">
            <div className="mb-3 flex items-center justify-between">
              <span className={cn(typography.xs)}>{item.label}</span>
              <div className={cn('flex h-10 w-10 items-center justify-center rounded-lg', item.bg)}>
                <item.icon className={cn('h-5 w-5', item.color)} />
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

  useRegisterPageContext(
    selectedCustomer
      ? { type: 'customer', id: selectedCustomer.id, name: selectedCustomer.name }
      : { type: 'crm' },
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
    <div className="space-y-6">
      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className={cn(typography.h1)}>客户管理</h1>
          <p className={cn(typography.small, 'mt-1 text-muted-foreground')}>
            管理客户关系、销售机会、跟进节奏和 AI 风险提示。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            className="gap-2"
            onClick={() =>
              triggerAI('请帮我快速记录一次客户拜访，提取客户名称、联系人、需求、异议、预算、下一步动作和跟进时间。')
            }
          >
            <Sparkles className="h-4 w-4" />
            记录拜访
          </Button>
          <Button className="gap-2" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
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
            {isFetchingNextPage ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                加载中...
              </>
            ) : (
              '加载更多'
            )}
          </Button>
        </div>
      )}

      <CustomerDetailSheet customer={selectedCustomer} open={detailOpen} onClose={() => setDetailOpen(false)} />
      <CustomerFormDialog open={createOpen} onClose={() => setCreateOpen(false)} />

      {editFromList && (
        <EditCustomerDialog customer={editFromList} open={!!editFromList} onClose={() => setEditFromList(null)} />
      )}

      <Dialog open={!!deleteFromList} onOpenChange={() => setDeleteFromList(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="h-5 w-5" />
              确认删除客户
            </DialogTitle>
            <DialogDescription>
              你即将删除客户 <strong>{deleteFromList?.name}</strong>。此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteFromList(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={async () => {
                if (!deleteFromList) return;
                try {
                  await deleteMutation.mutateAsync(deleteFromList.id);
                  setDeleteFromList(null);
                } catch {
                  toast.error('删除客户失败');
                }
              }}
            >
              {deleteMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              确认删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default CRMPage;
