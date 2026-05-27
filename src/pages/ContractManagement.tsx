/**
 * 合同生命周期管理
 * 合同 CRUD、状态管理、到期提醒、事件时间线
 */

import React, { useState, useMemo } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import {
  FileText,
  Plus,
  Search,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  DollarSign,
  Edit,
  Loader2,
  RefreshCw,
  Pen,
  FileCheck,
  Ban,
  RotateCw,
  Trash2,
  Sparkles,
} from 'lucide-react';
import { toast } from 'sonner';
import { useContracts, useContractDetail, useCreateContract, useDeleteContract, type Contract, type ContractEvent } from '@/hooks/useContracts';
import { useAuth } from '@/components/auth/AuthContext';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { AIInsightPanel } from '@/components/ai/AIInsightPanel';

// 合同类型
const CONTRACT_TYPES: Record<string, string> = {
  sales: '销售合同',
  purchase: '采购合同',
  service: '服务合同',
  nda: '保密协议',
  other: '其他',
};

// 合同状态配置
const CONTRACT_STATUS: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  draft: { label: '草稿', color: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300', icon: Edit },
  pending_review: { label: '审核中', color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300', icon: Clock },
  active: { label: '生效中', color: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300', icon: CheckCircle2 },
  expired: { label: '已过期', color: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300', icon: XCircle },
  terminated: { label: '已终止', color: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300', icon: Ban },
  renewed: { label: '已续约', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300', icon: RotateCw },
};

// 事件类型配置
const EVENT_TYPES: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  created: { label: '创建合同', icon: Plus, color: 'text-blue-500' },
  submitted: { label: '提交审核', icon: FileCheck, color: 'text-yellow-500' },
  approved: { label: '审核通过', icon: CheckCircle2, color: 'text-green-500' },
  signed: { label: '已签署', icon: Pen, color: 'text-purple-500' },
  amended: { label: '修订', icon: Edit, color: 'text-orange-500' },
  renewed: { label: '续约', icon: RefreshCw, color: 'text-blue-500' },
  expired: { label: '已过期', icon: Clock, color: 'text-red-500' },
  terminated: { label: '终止', icon: Ban, color: 'text-gray-500' },
};

// 格式化金额
function formatAmount(amount: number | null, currency: string = 'CNY') {
  if (amount === null || amount === undefined) return '--';
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency }).format(amount);
}

// 格式化日期
function formatDate(dateStr: string) {
  if (!dateStr) return '--';
  return new Date(dateStr).toLocaleDateString('zh-CN');
}

// 计算剩余天数
function daysUntil(dateStr: string) {
  if (!dateStr) return null;
  const diff = new Date(dateStr).getTime() - new Date().getTime();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function ContractAIInsightLayer({ contracts }: { contracts: Contract[] }) {
  const expiring = contracts.filter((contract) => {
    const days = daysUntil(contract.end_date);
    return contract.status === 'active' && days !== null && days >= 0 && days <= 30;
  });
  const pendingReview = contracts.filter((contract) => contract.status === 'pending_review');
  const highValue = [...contracts]
    .filter((contract) => Number(contract.amount) > 0)
    .sort((a, b) => Number(b.amount) - Number(a.amount))
    .slice(0, 1);
  const trustLevel = expiring.length > 0 || pendingReview.length > 0 ? 'medium' : 'high';

  return (
    <AIInsightPanel
      title="AI 合同风控摘要"
      icon={Sparkles}
      trustLevel={trustLevel}
      score={trustLevel === 'high' ? 90 : 76}
      summary={
        <>
          当前合同池中有 {pendingReview.length} 份待审核、{expiring.length} 份 30 天内到期
          {highValue[0] ? `，最高金额合同为 ${highValue[0].title}。` : '。'}
        </>
      }
      context={['合同台账', '到期日', '金额/客户主体']}
      evidence={[
        {
          label: '到期风险',
          value: (
            <>
              <span className="text-lg font-semibold">{expiring.length}</span>
              <span className="mt-1 block text-xs font-normal text-muted-foreground">建议优先触发续签或回款确认。</span>
            </>
          ),
        },
        {
          label: '待审核合同',
          value: (
            <>
              <span className="text-lg font-semibold">{pendingReview.length}</span>
              <span className="mt-1 block text-xs font-normal text-muted-foreground">金额、付款条款和客户主体需进入人审。</span>
            </>
          ),
        },
        {
          label: 'AI 证据',
          value: highValue[0]
            ? `${highValue[0].customer_name || '未关联客户'} / ${formatAmount(Number(highValue[0].amount))}`
            : '暂无高金额合同',
        },
      ]}
      risks={[
        ...(expiring.length > 0 ? ['存在 30 天内到期合同'] : []),
        ...(pendingReview.length > 0 ? ['存在待审核合同'] : []),
      ]}
      actions={[
        {
          label: '生成风险清单',
          prompt: '请基于当前合同台账，按金额、到期日、审核状态生成合同风险清单和处理优先级。',
        },
        {
          label: '今日合同计划',
          prompt: '请把当前即将到期和待审核合同整理成今天的合同处理计划。',
        },
      ]}
    />
  );
}

export function ContractManagement() {
  const [statusFilter, setStatusFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [selectedContractId, setSelectedContractId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    customer_name: '',
    contract_number: '',
    contract_type: 'sales',
    amount: '',
    start_date: '',
    end_date: '',
  });

  // Real data from Supabase
  const { data: allContracts = [], isLoading, error } = useContracts();
  const createMutation = useCreateContract();
  const deleteContract = useDeleteContract();
  const { role } = useAuth();
  const canDelete = role === 'boss' || role === 'admin';
  const { confirm, ConfirmDialogProps } = useConfirmDialog();

  // Events for selected contract
  const { data: selectedEvents = [] } = useContractDetail(selectedContractId);

  // Find the selected contract object
  const selectedContract = useMemo(
    () => allContracts.find(c => c.id === selectedContractId) || null,
    [allContracts, selectedContractId]
  );

  // Filter contracts client-side (search + status + expiring)
  const filteredContracts = useMemo(() => {
    return allContracts.filter((c) => {
      const matchStatus = statusFilter === 'all' || statusFilter === 'expiring'
        ? true
        : c.status === statusFilter;
      const matchSearch = !search
        || c.title.toLowerCase().includes(search.toLowerCase())
        || (c.customer_name || '').toLowerCase().includes(search.toLowerCase())
        || (c.contract_number || '').toLowerCase().includes(search.toLowerCase());

      if (statusFilter === 'expiring') {
        const days = daysUntil(c.end_date);
        return matchSearch && c.status === 'active' && days !== null && days >= 0 && days <= 30;
      }

      return matchStatus && matchSearch;
    });
  }, [allContracts, statusFilter, search]);

  // 统计数据
  const stats = useMemo(() => {
    const total = allContracts.length;
    const totalAmount = allContracts.reduce((acc, c) => acc + (Number(c.amount) || 0), 0);
    const active = allContracts.filter((c) => c.status === 'active').length;
    const expiring = allContracts.filter((c) => {
      const days = daysUntil(c.end_date);
      return c.status === 'active' && days !== null && days >= 0 && days <= 30;
    }).length;
    return { total, totalAmount, active, expiring };
  }, [allContracts]);

  // 打开详情
  const openDetail = (contract: Contract) => {
    setSelectedContractId(contract.id);
    setDetailOpen(true);
  };

  // 创建合同
  const handleCreate = async () => {
    if (!formData.title) {
      toast.error('请填写合同标题');
      return;
    }

    try {
      await createMutation.mutateAsync({
        title: formData.title,
        customer_name: formData.customer_name || undefined,
        contract_number: formData.contract_number || undefined,
        contract_type: formData.contract_type,
        amount: formData.amount ? parseFloat(formData.amount) : null,
        start_date: formData.start_date || undefined,
        end_date: formData.end_date || undefined,
      });

      setCreateDialogOpen(false);
      setFormData({
        title: '',
        customer_name: '',
        contract_number: '',
        contract_type: 'sales',
        amount: '',
        start_date: '',
        end_date: '',
      });
      toast.success('合同创建成功');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '创建失败';
      toast.error(`合同创建失败: ${message}`);
    }
  };

  const handleDeleteContract = async (contract: Contract) => {
    const ok = await confirm({
      title: '确认删除合同',
      description: `确定要删除合同「${contract.title}」吗？合同将被标记为已取消。`,
      variant: 'destructive',
      confirmText: '删除',
    });
    if (ok) {
      await deleteContract.mutateAsync(contract.id);
      setDetailOpen(false);
      setSelectedContractId(null);
    }
  };

  // 状态标签数量
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { all: allContracts.length };
    allContracts.forEach((c) => {
      counts[c.status] = (counts[c.status] || 0) + 1;
    });
    counts.expiring = allContracts.filter((c) => {
      const days = daysUntil(c.end_date);
      return c.status === 'active' && days !== null && days >= 0 && days <= 30;
    }).length;
    return counts;
  }, [allContracts]);

  // 时间线渲染
  const renderTimeline = (events: ContractEvent[]) => {
    const sorted = [...events].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    if (sorted.length === 0) {
      return <p className="text-sm text-muted-foreground">暂无事件记录</p>;
    }

    return (
      <div className="space-y-4">
        {sorted.map((event, idx) => {
          const config = EVENT_TYPES[event.event_type] || EVENT_TYPES.created;
          const IconComp = config.icon;

          return (
            <div key={event.id} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className={cn('w-8 h-8 rounded-full flex items-center justify-center bg-muted', config.color)}>
                  <IconComp className="h-4 w-4" />
                </div>
                {idx < sorted.length - 1 && (
                  <div className="w-px flex-1 bg-border mt-1" />
                )}
              </div>
              <div className="flex-1 pb-4">
                <p className="text-sm font-medium">{config.label}</p>
                <p className="text-xs text-muted-foreground">{event.description}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {new Date(event.created_at).toLocaleString('zh-CN')}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  if (error) {
    return (
      <div className="p-6 text-center">
        <p className="text-destructive">加载合同数据失败: {(error as Error).message}</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      {/* 页面标题 */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileText className="h-6 w-6 text-primary" />
            合同管理
          </h1>
          <p className="text-muted-foreground mt-1">管理合同全生命周期</p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" />
          新建合同
        </Button>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900">
              <FileText className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{isLoading ? '-' : stats.total}</p>
              <p className="text-xs text-muted-foreground">合同总数</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-100 dark:bg-green-900">
              <DollarSign className="h-5 w-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{isLoading ? '-' : formatAmount(stats.totalAmount)}</p>
              <p className="text-xs text-muted-foreground">合同总额</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900">
              <CheckCircle2 className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{isLoading ? '-' : stats.active}</p>
              <p className="text-xs text-muted-foreground">生效中</p>
            </div>
          </CardContent>
        </Card>
        <Card className={stats.expiring > 0 ? 'border-orange-300 dark:border-orange-700' : ''}>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-orange-100 dark:bg-orange-900">
              <AlertTriangle className="h-5 w-5 text-orange-600 dark:text-orange-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{isLoading ? '-' : stats.expiring}</p>
              <p className="text-xs text-muted-foreground">即将到期 (30天内)</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <ContractAIInsightLayer contracts={allContracts} />

      {/* 搜索和筛选 */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="搜索合同标题、客户、编号..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* 状态筛选 Tabs */}
      <Tabs value={statusFilter} onValueChange={setStatusFilter}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="all">全部 ({statusCounts.all || 0})</TabsTrigger>
          <TabsTrigger value="draft">草稿 ({statusCounts.draft || 0})</TabsTrigger>
          <TabsTrigger value="pending_review">审核中 ({statusCounts.pending_review || 0})</TabsTrigger>
          <TabsTrigger value="active">生效中 ({statusCounts.active || 0})</TabsTrigger>
          <TabsTrigger value="expiring" className="text-orange-600 dark:text-orange-400">
            即将到期 ({statusCounts.expiring || 0})
          </TabsTrigger>
          <TabsTrigger value="expired">已过期 ({statusCounts.expired || 0})</TabsTrigger>
        </TabsList>
      </Tabs>

      {/* 合同列表 */}
      {isLoading ? (
        <div className="text-center py-16">
          <Loader2 className="h-8 w-8 mx-auto animate-spin text-muted-foreground" />
          <p className="text-muted-foreground mt-2">加载中...</p>
        </div>
      ) : filteredContracts.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <FileText className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p>没有找到匹配的合同</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredContracts.map((contract) => {
            const statusConfig = CONTRACT_STATUS[contract.status] || CONTRACT_STATUS.draft;
            const StatusIcon = statusConfig.icon;
            const remainDays = daysUntil(contract.end_date);
            const isExpiringSoon = contract.status === 'active' && remainDays !== null && remainDays >= 0 && remainDays <= 30;

            return (
              <Card
                key={contract.id}
                className={cn(
                  'cursor-pointer hover:shadow-md transition-all',
                  isExpiringSoon && 'border-orange-200 dark:border-orange-800'
                )}
                onClick={() => openDetail(contract)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-4">
                    {/* 左侧状态图标 */}
                    <div className={cn('p-2 rounded-lg shrink-0', statusConfig.color)}>
                      <StatusIcon className="h-5 w-5" />
                    </div>

                    {/* 中间内容 */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-semibold text-sm truncate">{contract.title}</h3>
                        <Badge className={cn('text-[10px] shrink-0', statusConfig.color)}>
                          {statusConfig.label}
                        </Badge>
                        {isExpiringSoon && (
                          <Badge variant="outline" className="text-[10px] text-orange-600 border-orange-300 shrink-0">
                            {remainDays}天后到期
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground flex-wrap">
                        {contract.customer_name && <span>{contract.customer_name}</span>}
                        {contract.contract_number && <span>{contract.contract_number}</span>}
                        <span>{CONTRACT_TYPES[contract.contract_type] || contract.contract_type}</span>
                      </div>
                    </div>

                    {/* 右侧金额和日期 */}
                    <div className="text-right shrink-0">
                      <p className="font-bold text-sm">
                        {contract.amount !== null ? formatAmount(Number(contract.amount)) : '--'}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {contract.start_date && contract.end_date
                          ? `${formatDate(contract.start_date)} ~ ${formatDate(contract.end_date)}`
                          : '日期待定'}
                      </p>
                    </div>
                  </div>

                  {/* 标签 */}
                  {contract.tags && contract.tags.length > 0 && (
                    <div className="flex gap-1.5 mt-2 ml-12">
                      {contract.tags.map((tag) => (
                        <Badge key={tag} variant="secondary" className="text-[10px]">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* 合同详情侧边栏 */}
      <Sheet open={detailOpen} onOpenChange={(open) => { setDetailOpen(open); if (!open) setSelectedContractId(null); }}>
        <SheetContent className="sm:max-w-lg">
          {selectedContract && (
            <>
              <SheetHeader>
                <SheetTitle className="text-lg">{selectedContract.title}</SheetTitle>
                <SheetDescription>{selectedContract.contract_number || '无编号'}</SheetDescription>
              </SheetHeader>

              <ScrollArea className="mt-6 h-[calc(100dvh-120px)]">
                <div className="space-y-6 pr-4">
                  {/* 基本信息 */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold">基本信息</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <p className="text-xs text-muted-foreground">客户</p>
                        <p className="text-sm font-medium">{selectedContract.customer_name || '--'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">合同类型</p>
                        <p className="text-sm font-medium">
                          {CONTRACT_TYPES[selectedContract.contract_type] || selectedContract.contract_type}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">状态</p>
                        <Badge className={cn('text-xs', CONTRACT_STATUS[selectedContract.status]?.color)}>
                          {CONTRACT_STATUS[selectedContract.status]?.label || selectedContract.status}
                        </Badge>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">金额</p>
                        <p className="text-sm font-bold text-primary">
                          {formatAmount(Number(selectedContract.amount), selectedContract.currency)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">开始日期</p>
                        <p className="text-sm">{formatDate(selectedContract.start_date)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">结束日期</p>
                        <p className="text-sm">{formatDate(selectedContract.end_date)}</p>
                      </div>
                    </div>

                    {/* 到期提醒 */}
                    {selectedContract.status === 'active' && selectedContract.end_date && (() => {
                      const days = daysUntil(selectedContract.end_date);
                      if (days !== null && days >= 0 && days <= 30) {
                        return (
                          <div className="p-3 rounded-lg bg-orange-50 border border-orange-200 dark:bg-orange-950 dark:border-orange-800">
                            <div className="flex items-center gap-2 text-orange-700 dark:text-orange-300">
                              <AlertTriangle className="h-4 w-4" />
                              <span className="text-sm font-medium">
                                距到期还有 {days} 天，请及时处理续约事宜
                              </span>
                            </div>
                          </div>
                        );
                      }
                      return null;
                    })()}
                  </div>

                  <Separator />

                  {/* 事件时间线 */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold">合同时间线</h4>
                    {renderTimeline(selectedEvents)}
                  </div>

                  {/* 删除操作 */}
                  {canDelete && (
                    <>
                      <Separator />
                      <div className="flex justify-end">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
                          onClick={() => handleDeleteContract(selectedContract)}
                          disabled={deleteContract.isPending}
                        >
                          <Trash2 className="w-4 h-4 mr-1" /> 删除合同
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              </ScrollArea>
            </>
          )}
        </SheetContent>
      </Sheet>

      {/* 新建合同弹窗 */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="h-4 w-4" />
              新建合同
            </DialogTitle>
            <DialogDescription>
              填写合同基本信息，创建后可继续编辑
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>合同标题 <span className="text-red-500">*</span></Label>
              <Input
                placeholder="输入合同标题"
                value={formData.title}
                onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>客户名称</Label>
                <Input
                  placeholder="客户公司名称"
                  value={formData.customer_name}
                  onChange={(e) => setFormData((prev) => ({ ...prev, customer_name: e.target.value }))}
                />
              </div>
              <div className="space-y-1.5">
                <Label>合同编号</Label>
                <Input
                  placeholder="自动生成"
                  value={formData.contract_number}
                  onChange={(e) => setFormData((prev) => ({ ...prev, contract_number: e.target.value }))}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>合同类型</Label>
                <Select
                  value={formData.contract_type}
                  onValueChange={(val) => setFormData((prev) => ({ ...prev, contract_type: val }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(CONTRACT_TYPES).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>合同金额 (CNY)</Label>
                <Input
                  type="number"
                  placeholder="0.00"
                  value={formData.amount}
                  onChange={(e) => setFormData((prev) => ({ ...prev, amount: e.target.value }))}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>开始日期</Label>
                <Input
                  type="date"
                  value={formData.start_date}
                  onChange={(e) => setFormData((prev) => ({ ...prev, start_date: e.target.value }))}
                />
              </div>
              <div className="space-y-1.5">
                <Label>结束日期</Label>
                <Input
                  type="date"
                  value={formData.end_date}
                  onChange={(e) => setFormData((prev) => ({ ...prev, end_date: e.target.value }))}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              创建合同
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog {...ConfirmDialogProps} />
    </div>
  );
}

export default ContractManagement;
