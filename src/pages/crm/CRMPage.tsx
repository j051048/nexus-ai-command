import React, { useState, useMemo } from 'react';
import { useDebounce } from '@/hooks/useDebounce';
import { NoDataYet, NoSearchResults } from '@/components/common/EmptyState';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
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

function StatsBar() {
  const { data: stats, isLoading } = useCustomerStats();

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[1, 2, 3, 4, 5].map(i => <Skeleton key={i} className="h-20" />)}
      </div>
    );
  }

  const items = [
    { label: '客户总数', value: stats?.total_customers ?? 0, icon: Users, color: 'text-blue-500' },
    { label: '本月新增', value: stats?.new_this_month ?? 0, icon: Plus, color: 'text-green-500' },
    { label: '转化率', value: `${stats?.conversion_rate ?? 0}%`, icon: ArrowRightLeft, color: 'text-orange-500' },
    { label: '预估总额', value: `\u00A5${Number(stats?.total_estimated_value ?? 0).toLocaleString()}`, icon: DollarSign, color: 'text-purple-500' },
    { label: '流失', value: stats?.churned ?? 0, icon: TrendingUp, color: 'text-red-500' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      {items.map(item => (
        <Card key={item.label}>
          <CardContent className="pt-4 pb-3 px-4">
            <div className="flex items-center gap-2">
              <item.icon className={cn('w-4 h-4', item.color)} />
              <span className="text-xs text-muted-foreground">{item.label}</span>
            </div>
            <p className={cn('text-lg font-bold mt-1', item.color)}>{item.value}</p>
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

  const filters = useMemo(() => {
    const f: Record<string, string> = {};
    if (stageFilter !== 'all') f.stage = stageFilter;
    if (debouncedSearch) f.search = debouncedSearch;
    return f;
  }, [stageFilter, debouncedSearch]);

  const { data: customersData, isLoading } = useCustomers(filters);
  const customers = (customersData || []) as Customer[];

  const handleSelectCustomer = (customer: Customer) => {
    setSelectedCustomer(customer);
    setDetailOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">客户管理</h1>
          <p className="text-muted-foreground">管理客户关系，跟踪销售漏斗</p>
        </div>
        <Button className="gap-2" onClick={() => setCreateOpen(true)}>
          <Plus className="w-4 h-4" />
          新建客户
        </Button>
      </div>

      <StatsBar />

      <CustomerFilters
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        stageFilter={stageFilter}
        onStageFilterChange={setStageFilter}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        customers={customers as unknown as Record<string, unknown>[]}
      />

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-6 w-20" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ))}
        </div>
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
