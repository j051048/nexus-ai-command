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
        <Button className="gap-2" onClick={() => setCreateOpen(true)}>
          <Plus className="w-4 h-4" />
          新建客户
        </Button>
      </div>

      <StatsBar />

      <AIQuickActions pageType="crm" />

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
