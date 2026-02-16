/**
 * 合同生命周期管理
 * 合同 CRUD、状态管理、到期提醒、事件时间线
 */

import React, { useState, useMemo } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
  Filter,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  DollarSign,
  Calendar,
  TrendingUp,
  Eye,
  Edit,
  Loader2,
  ArrowUpDown,
  RefreshCw,
  Pen,
  FileCheck,
  Ban,
  RotateCw,
} from 'lucide-react';
import { toast } from 'sonner';

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

interface ContractEvent {
  id: string;
  contract_id: string;
  event_type: string;
  description: string;
  user_id?: string;
  created_at: string;
}

interface Contract {
  id: string;
  title: string;
  customer_name?: string;
  contract_number: string;
  contract_type: string;
  status: string;
  amount: number | null;
  currency: string;
  start_date: string;
  end_date: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  events: ContractEvent[];
}

// 模拟合同数据
const MOCK_CONTRACTS: Contract[] = [
  {
    id: '1',
    title: '华为云 SaaS 服务合同',
    customer_name: '华为技术有限公司',
    contract_number: 'CT-2026-001',
    contract_type: 'sales',
    status: 'active',
    amount: 580000,
    currency: 'CNY',
    start_date: '2026-01-01',
    end_date: '2026-12-31',
    tags: ['大客户', '年度合同'],
    created_at: '2025-12-15T10:00:00Z',
    updated_at: '2026-01-05T09:00:00Z',
    events: [
      { id: 'e1', contract_id: '1', event_type: 'created', description: '合同创建', created_at: '2025-12-15T10:00:00Z' },
      { id: 'e2', contract_id: '1', event_type: 'submitted', description: '提交法务审核', created_at: '2025-12-18T14:00:00Z' },
      { id: 'e3', contract_id: '1', event_type: 'approved', description: '法务审核通过', created_at: '2025-12-22T11:00:00Z' },
      { id: 'e4', contract_id: '1', event_type: 'signed', description: '双方签署合同', created_at: '2026-01-02T16:00:00Z' },
    ],
  },
  {
    id: '2',
    title: '腾讯数据安全保密协议',
    customer_name: '深圳市腾讯计算机系统有限公司',
    contract_number: 'CT-2026-002',
    contract_type: 'nda',
    status: 'active',
    amount: null,
    currency: 'CNY',
    start_date: '2026-02-01',
    end_date: '2027-01-31',
    tags: ['保密协议'],
    created_at: '2026-01-20T08:00:00Z',
    updated_at: '2026-02-01T09:00:00Z',
    events: [
      { id: 'e5', contract_id: '2', event_type: 'created', description: '保密协议创建', created_at: '2026-01-20T08:00:00Z' },
      { id: 'e6', contract_id: '2', event_type: 'signed', description: '双方签署', created_at: '2026-02-01T09:00:00Z' },
    ],
  },
  {
    id: '3',
    title: '阿里巴巴年度采购合同',
    customer_name: '阿里巴巴集团',
    contract_number: 'CT-2026-003',
    contract_type: 'purchase',
    status: 'pending_review',
    amount: 320000,
    currency: 'CNY',
    start_date: '2026-03-01',
    end_date: '2027-02-28',
    tags: ['采购'],
    created_at: '2026-02-10T10:00:00Z',
    updated_at: '2026-02-10T10:00:00Z',
    events: [
      { id: 'e7', contract_id: '3', event_type: 'created', description: '合同创建', created_at: '2026-02-10T10:00:00Z' },
      { id: 'e8', contract_id: '3', event_type: 'submitted', description: '提交审核', created_at: '2026-02-12T09:00:00Z' },
    ],
  },
  {
    id: '4',
    title: '字节跳动技术咨询服务',
    customer_name: '北京字节跳动科技有限公司',
    contract_number: 'CT-2025-045',
    contract_type: 'service',
    status: 'active',
    amount: 150000,
    currency: 'CNY',
    start_date: '2025-09-01',
    end_date: '2026-02-28',
    tags: ['即将到期'],
    created_at: '2025-08-20T10:00:00Z',
    updated_at: '2025-09-01T09:00:00Z',
    events: [
      { id: 'e9', contract_id: '4', event_type: 'created', description: '合同创建', created_at: '2025-08-20T10:00:00Z' },
      { id: 'e10', contract_id: '4', event_type: 'signed', description: '签署', created_at: '2025-09-01T09:00:00Z' },
    ],
  },
  {
    id: '5',
    title: '小米智能硬件合同',
    customer_name: '小米科技有限责任公司',
    contract_number: 'CT-2025-030',
    contract_type: 'sales',
    status: 'expired',
    amount: 420000,
    currency: 'CNY',
    start_date: '2025-01-01',
    end_date: '2025-12-31',
    tags: ['已过期'],
    created_at: '2024-12-10T10:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    events: [
      { id: 'e11', contract_id: '5', event_type: 'created', description: '合同创建', created_at: '2024-12-10T10:00:00Z' },
      { id: 'e12', contract_id: '5', event_type: 'signed', description: '签署生效', created_at: '2025-01-01T09:00:00Z' },
      { id: 'e13', contract_id: '5', event_type: 'expired', description: '合同到期', created_at: '2026-01-01T00:00:00Z' },
    ],
  },
  {
    id: '6',
    title: '美团合作框架协议',
    customer_name: '北京三快科技有限公司',
    contract_number: 'CT-2026-004',
    contract_type: 'other',
    status: 'draft',
    amount: 200000,
    currency: 'CNY',
    start_date: '',
    end_date: '',
    tags: ['草稿'],
    created_at: '2026-02-13T10:00:00Z',
    updated_at: '2026-02-13T10:00:00Z',
    events: [
      { id: 'e14', contract_id: '6', event_type: 'created', description: '草稿创建', created_at: '2026-02-13T10:00:00Z' },
    ],
  },
];

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

export function ContractManagement() {
  const [contracts, setContracts] = useState<Contract[]>(MOCK_CONTRACTS);
  const [statusFilter, setStatusFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [selectedContract, setSelectedContract] = useState<Contract | null>(null);
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

  // 筛选合同
  const filteredContracts = useMemo(() => {
    return contracts.filter((c) => {
      const matchStatus = statusFilter === 'all' || statusFilter === 'expiring'
        ? true
        : c.status === statusFilter;
      const matchSearch = !search
        || c.title.toLowerCase().includes(search.toLowerCase())
        || c.customer_name?.toLowerCase().includes(search.toLowerCase())
        || c.contract_number.toLowerCase().includes(search.toLowerCase());

      if (statusFilter === 'expiring') {
        const days = daysUntil(c.end_date);
        return matchSearch && c.status === 'active' && days !== null && days >= 0 && days <= 30;
      }

      return matchStatus && matchSearch;
    });
  }, [contracts, statusFilter, search]);

  // 统计数据
  const stats = useMemo(() => {
    const total = contracts.length;
    const totalAmount = contracts.reduce((acc, c) => acc + (c.amount || 0), 0);
    const active = contracts.filter((c) => c.status === 'active').length;
    const expiring = contracts.filter((c) => {
      const days = daysUntil(c.end_date);
      return c.status === 'active' && days !== null && days >= 0 && days <= 30;
    }).length;
    return { total, totalAmount, active, expiring };
  }, [contracts]);

  // 打开详情
  const openDetail = (contract: Contract) => {
    setSelectedContract(contract);
    setDetailOpen(true);
  };

  // 创建合同
  const handleCreate = () => {
    if (!formData.title) {
      toast.error('请填写合同标题');
      return;
    }

    const newContract: Contract = {
      id: `new-${Date.now()}`,
      title: formData.title,
      customer_name: formData.customer_name,
      contract_number: formData.contract_number || `CT-2026-${(contracts.length + 1).toString().padStart(3, '0')}`,
      contract_type: formData.contract_type,
      status: 'draft',
      amount: formData.amount ? parseFloat(formData.amount) : null,
      currency: 'CNY',
      start_date: formData.start_date,
      end_date: formData.end_date,
      tags: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      events: [
        {
          id: `evt-${Date.now()}`,
          contract_id: `new-${Date.now()}`,
          event_type: 'created',
          description: '合同创建',
          created_at: new Date().toISOString(),
        },
      ],
    };

    setContracts((prev) => [newContract, ...prev]);
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
  };

  // 状态标签数量
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { all: contracts.length };
    contracts.forEach((c) => {
      counts[c.status] = (counts[c.status] || 0) + 1;
    });
    counts.expiring = contracts.filter((c) => {
      const days = daysUntil(c.end_date);
      return c.status === 'active' && days !== null && days >= 0 && days <= 30;
    }).length;
    return counts;
  }, [contracts]);

  // 时间线渲染
  const renderTimeline = (events: ContractEvent[]) => {
    const sorted = [...events].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

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

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
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
              <p className="text-2xl font-bold">{stats.total}</p>
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
              <p className="text-2xl font-bold">{formatAmount(stats.totalAmount)}</p>
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
              <p className="text-2xl font-bold">{stats.active}</p>
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
              <p className="text-2xl font-bold">{stats.expiring}</p>
              <p className="text-xs text-muted-foreground">即将到期 (30天内)</p>
            </div>
          </CardContent>
        </Card>
      </div>

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
      {filteredContracts.length === 0 ? (
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
                        <span>{contract.contract_number}</span>
                        <span>{CONTRACT_TYPES[contract.contract_type] || contract.contract_type}</span>
                      </div>
                    </div>

                    {/* 右侧金额和日期 */}
                    <div className="text-right shrink-0">
                      <p className="font-bold text-sm">
                        {contract.amount !== null ? formatAmount(contract.amount) : '--'}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {contract.start_date && contract.end_date
                          ? `${formatDate(contract.start_date)} ~ ${formatDate(contract.end_date)}`
                          : '日期待定'}
                      </p>
                    </div>
                  </div>

                  {/* 标签 */}
                  {contract.tags.length > 0 && (
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
      <Sheet open={detailOpen} onOpenChange={setDetailOpen}>
        <SheetContent className="sm:max-w-lg">
          {selectedContract && (
            <>
              <SheetHeader>
                <SheetTitle className="text-lg">{selectedContract.title}</SheetTitle>
                <SheetDescription>{selectedContract.contract_number}</SheetDescription>
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
                          {formatAmount(selectedContract.amount, selectedContract.currency)}
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
                    {renderTimeline(selectedContract.events)}
                  </div>
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
            <Button onClick={handleCreate}>
              创建合同
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default ContractManagement;
