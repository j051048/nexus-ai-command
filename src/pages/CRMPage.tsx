/**
 * CRM 客户关系管理页面
 * 看板/列表视图、客户详情侧边栏、新建编辑弹窗、搜索筛选
 */

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import {
  Search,
  Plus,
  Users,
  Building2,
  Phone,
  Mail,
  Calendar,
  FileText,
  TrendingUp,
  LayoutGrid,
  List,
  ChevronRight,
  User2,
  DollarSign,
  MessageSquare,
  Clock,
  ArrowRightLeft,
} from 'lucide-react';
import { useCustomers, useCustomerTimeline, useCustomerContacts, useCreateCustomer, useCustomerStats, useUpdateCustomer } from '@/hooks/useCRM';
import type { Customer, CustomerActivity, CustomerContact } from '@/hooks/useCRM';
import { toast } from 'sonner';
import { DataExport } from '@/components/common/DataExport';
import type { ExportColumn } from '@/components/common/DataExport';

// 阶段配置
const STAGES: Record<string, { name: string; color: string; bg: string }> = {
  lead: { name: '线索', color: 'text-slate-600', bg: 'bg-slate-100 dark:bg-slate-800' },
  prospect: { name: '意向', color: 'text-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/30' },
  opportunity: { name: '商机', color: 'text-amber-600', bg: 'bg-amber-100 dark:bg-amber-900/30' },
  customer: { name: '成交', color: 'text-green-600', bg: 'bg-green-100 dark:bg-green-900/30' },
  churned: { name: '流失', color: 'text-red-600', bg: 'bg-red-100 dark:bg-red-900/30' },
};

// 导出列配置
const CRM_EXPORT_COLUMNS: ExportColumn[] = [
  { key: 'name', label: '客户名称' },
  { key: 'company', label: '公司' },
  { key: 'industry', label: '行业' },
  { key: 'stage', label: '阶段', formatter: (value) => STAGES[value as string]?.name || String(value ?? '') },
  { key: 'estimated_value', label: '预估金额', formatter: (value) => value ? `\u00A5${Number(value).toLocaleString()}` : '' },
  { key: 'source', label: '来源' },
];

const ACTIVITY_ICONS: Record<string, React.ReactNode> = {
  call: <Phone className="w-4 h-4" />,
  email: <Mail className="w-4 h-4" />,
  meeting: <Calendar className="w-4 h-4" />,
  note: <FileText className="w-4 h-4" />,
  deal_update: <TrendingUp className="w-4 h-4" />,
};

const ACTIVITY_NAMES: Record<string, string> = {
  call: '电话',
  email: '邮件',
  meeting: '会议',
  note: '备注',
  deal_update: '交易更新',
};

/* ────────────────── Stat Cards ────────────────── */
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

/* ────────────────── Customer Card ────────────────── */
function CustomerCard({ customer, onClick }: { customer: Customer; onClick: () => void }) {
  const stage = STAGES[customer.stage] || STAGES.lead;
  return (
    <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={onClick}>
      <CardContent className="p-4 space-y-2">
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <h4 className="font-medium truncate">{customer.name}</h4>
            <p className="text-xs text-muted-foreground truncate">{customer.company}</p>
          </div>
          <Badge className={cn('shrink-0 text-xs', stage.color, stage.bg)}>{stage.name}</Badge>
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{customer.industry}</span>
          {customer.estimated_value > 0 && (
            <span className="font-medium">{'\u00A5'}{Number(customer.estimated_value).toLocaleString()}</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/* ────────────────── Kanban View ────────────────── */
function KanbanView({
  customers,
  onSelect,
}: {
  customers: Customer[];
  onSelect: (c: Customer) => void;
}) {
  const columns = ['lead', 'prospect', 'opportunity', 'customer'];

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {columns.map(stageKey => {
        const stage = STAGES[stageKey];
        const stageCustomers = customers.filter(c => c.stage === stageKey);
        return (
          <div key={stageKey} className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className={cn('font-medium text-sm', stage.color)}>{stage.name}</h3>
              <Badge variant="outline" className="text-xs">{stageCustomers.length}</Badge>
            </div>
            <div className="space-y-2 min-h-[200px]">
              {stageCustomers.map(c => (
                <CustomerCard key={c.id} customer={c} onClick={() => onSelect(c)} />
              ))}
              {stageCustomers.length === 0 && (
                <div className="text-center py-8 text-sm text-muted-foreground border border-dashed rounded-lg">
                  暂无客户
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ────────────────── List View ────────────────── */
function ListView({
  customers,
  onSelect,
}: {
  customers: Customer[];
  onSelect: (c: Customer) => void;
}) {
  return (
    <div className="space-y-2">
      {/* 表头 */}
      <div className="grid grid-cols-3 md:grid-cols-7 lg:grid-cols-12 gap-2 px-4 py-2 text-xs font-medium text-muted-foreground">
        <div className="col-span-1 md:col-span-2 lg:col-span-3">客户名称</div>
        <div className="hidden md:block md:col-span-1 lg:col-span-2">公司</div>
        <div className="hidden md:block md:col-span-1 lg:col-span-1">行业</div>
        <div className="col-span-1 md:col-span-1 lg:col-span-1">阶段</div>
        <div className="hidden md:block md:col-span-1 lg:col-span-2">预估金额</div>
        <div className="hidden lg:block lg:col-span-2">来源</div>
        <div className="col-span-1 md:col-span-1 lg:col-span-1">操作</div>
      </div>
      {customers.map(c => {
        const stage = STAGES[c.stage] || STAGES.lead;
        return (
          <div
            key={c.id}
            className="grid grid-cols-3 md:grid-cols-7 lg:grid-cols-12 gap-2 px-4 py-3 rounded-lg border items-center hover:bg-muted/50 cursor-pointer transition"
            onClick={() => onSelect(c)}
          >
            <div className="col-span-1 md:col-span-2 lg:col-span-3 font-medium truncate">{c.name}</div>
            <div className="hidden md:block md:col-span-1 lg:col-span-2 text-sm text-muted-foreground truncate">{c.company}</div>
            <div className="hidden md:block md:col-span-1 lg:col-span-1 text-sm text-muted-foreground">{c.industry}</div>
            <div className="col-span-1 md:col-span-1 lg:col-span-1">
              <Badge className={cn('text-xs', stage.color, stage.bg)}>{stage.name}</Badge>
            </div>
            <div className="hidden md:block md:col-span-1 lg:col-span-2 text-sm font-medium">
              {c.estimated_value > 0 ? `\u00A5${Number(c.estimated_value).toLocaleString()}` : '-'}
            </div>
            <div className="hidden lg:block lg:col-span-2 text-sm text-muted-foreground">{c.source || '-'}</div>
            <div className="col-span-1 md:col-span-1 lg:col-span-1">
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ────────────────── Detail Sidebar ────────────────── */
function CustomerDetailSheet({
  customer,
  open,
  onClose,
}: {
  customer: Customer | null;
  open: boolean;
  onClose: () => void;
}) {
  const { data: timeline = [], isLoading: timelineLoading } = useCustomerTimeline(customer?.id || null);
  const { data: contacts = [], isLoading: contactsLoading } = useCustomerContacts(customer?.id || null);

  if (!customer) return null;

  const stage = STAGES[customer.stage] || STAGES.lead;

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader className="mb-6">
          <SheetTitle className="flex items-center gap-2">
            <Building2 className="w-5 h-5" />
            {customer.name}
          </SheetTitle>
          <SheetDescription>{customer.company}</SheetDescription>
        </SheetHeader>

        {/* 基本信息 */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Badge className={cn('text-sm', stage.color, stage.bg)}>{stage.name}</Badge>
            {customer.estimated_value > 0 && (
              <span className="text-lg font-bold">{'\u00A5'}{Number(customer.estimated_value).toLocaleString()}</span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-muted-foreground">行业</span>
              <p className="font-medium">{customer.industry || '-'}</p>
            </div>
            <div>
              <span className="text-muted-foreground">来源</span>
              <p className="font-medium">{customer.source || '-'}</p>
            </div>
            <div>
              <span className="text-muted-foreground">创建时间</span>
              <p className="font-medium">{new Date(customer.created_at).toLocaleDateString('zh-CN')}</p>
            </div>
            <div>
              <span className="text-muted-foreground">更新时间</span>
              <p className="font-medium">{new Date(customer.updated_at).toLocaleDateString('zh-CN')}</p>
            </div>
          </div>

          <Separator />

          {/* 联系人 */}
          <div>
            <h4 className="font-medium mb-3 flex items-center gap-2">
              <User2 className="w-4 h-4" />
              联系人
            </h4>
            {contactsLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : (contacts as CustomerContact[]).length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无联系人</p>
            ) : (
              <div className="space-y-2">
                {(contacts as CustomerContact[]).map(contact => (
                  <div key={contact.id} className="flex items-center justify-between p-2 rounded-lg border">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{contact.name}</span>
                        {contact.is_primary && <Badge variant="secondary" className="text-xs">主要</Badge>}
                      </div>
                      <p className="text-xs text-muted-foreground">{contact.title}</p>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      {contact.phone && (
                        <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{contact.phone}</span>
                      )}
                      {contact.email && (
                        <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{contact.email}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <Separator />

          {/* 活动时间线 */}
          <div>
            <h4 className="font-medium mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4" />
              活动时间线
            </h4>
            {timelineLoading ? (
              <div className="space-y-2">{[1, 2, 3].map(i => <Skeleton key={i} className="h-12 w-full" />)}</div>
            ) : (timeline as CustomerActivity[]).length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无活动记录</p>
            ) : (
              <ScrollArea className="h-[300px]">
                <div className="space-y-3">
                  {(timeline as CustomerActivity[]).map(act => (
                    <div key={act.id} className="flex gap-3">
                      <div className="mt-1 p-1.5 rounded-full bg-muted shrink-0">
                        {ACTIVITY_ICONS[act.activity_type] || <MessageSquare className="w-4 h-4" />}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{ACTIVITY_NAMES[act.activity_type] || act.activity_type}</span>
                          <span className="text-xs text-muted-foreground">
                            {new Date(act.created_at).toLocaleDateString('zh-CN')}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground">{act.content}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

/* ────────────────── Create Dialog ────────────────── */
function CreateCustomerDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const createMutation = useCreateCustomer();
  const [form, setForm] = useState({
    name: '',
    company: '',
    industry: '',
    stage: 'lead',
    source: '',
    estimated_value: '',
  });

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      toast.error('请输入客户名称');
      return;
    }
    try {
      await createMutation.mutateAsync({
        name: form.name,
        company: form.company,
        industry: form.industry,
        stage: form.stage,
        source: form.source,
        estimated_value: form.estimated_value ? Number(form.estimated_value) : 0,
      });
      toast.success('客户创建成功');
      setForm({ name: '', company: '', industry: '', stage: 'lead', source: '', estimated_value: '' });
      onClose();
    } catch {
      toast.error('创建失败，请重试');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建客户</DialogTitle>
          <DialogDescription>填写客户基本信息</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>客户名称 *</Label>
            <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="项目或客户名称" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>公司</Label>
              <Input value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} placeholder="公司名称" />
            </div>
            <div className="space-y-2">
              <Label>行业</Label>
              <Input value={form.industry} onChange={e => setForm({ ...form, industry: e.target.value })} placeholder="行业领域" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>阶段</Label>
              <Select value={form.stage} onValueChange={v => setForm({ ...form, stage: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(STAGES).map(([key, val]) => (
                    <SelectItem key={key} value={key}>{val.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>来源</Label>
              <Select value={form.source} onValueChange={v => setForm({ ...form, source: v })}>
                <SelectTrigger><SelectValue placeholder="选择来源" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="website">网站</SelectItem>
                  <SelectItem value="referral">转介绍</SelectItem>
                  <SelectItem value="exhibition">展会</SelectItem>
                  <SelectItem value="cold_call">Cold Call</SelectItem>
                  <SelectItem value="other">其他</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label>预估金额</Label>
            <Input type="number" value={form.estimated_value} onChange={e => setForm({ ...form, estimated_value: e.target.value })} placeholder="预估交易金额" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={createMutation.isPending}>
            {createMutation.isPending ? '创建中...' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ────────────────── Main Page ────────────────── */
function CRMPage() {
  const [viewMode, setViewMode] = useState<'kanban' | 'list'>('kanban');
  const [searchQuery, setSearchQuery] = useState('');
  const [stageFilter, setStageFilter] = useState('all');
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  const filters = useMemo(() => {
    const f: Record<string, string> = {};
    if (stageFilter !== 'all') f.stage = stageFilter;
    if (searchQuery) f.search = searchQuery;
    return f;
  }, [stageFilter, searchQuery]);

  const { data: customersData, isLoading } = useCustomers(filters);
  const customers = (customersData || []) as Customer[];

  const handleSelectCustomer = (customer: Customer) => {
    setSelectedCustomer(customer);
    setDetailOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
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

      {/* 统计卡片 */}
      <StatsBar />

      {/* 工具栏 */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            className="pl-10"
            placeholder="搜索客户名称或公司..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
        </div>
        <Select value={stageFilter} onValueChange={setStageFilter}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="全部阶段" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部阶段</SelectItem>
            {Object.entries(STAGES).map(([key, val]) => (
              <SelectItem key={key} value={key}>{val.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-1 border rounded-md">
          <Button
            variant={viewMode === 'kanban' ? 'default' : 'ghost'}
            size="sm"
            className="gap-1 rounded-r-none"
            onClick={() => setViewMode('kanban')}
          >
            <LayoutGrid className="w-4 h-4" />
            看板
          </Button>
          <Button
            variant={viewMode === 'list' ? 'default' : 'ghost'}
            size="sm"
            className="gap-1 rounded-l-none"
            onClick={() => setViewMode('list')}
          >
            <List className="w-4 h-4" />
            列表
          </Button>
        </div>
        <DataExport
          data={customers as unknown as Record<string, unknown>[]}
          columns={CRM_EXPORT_COLUMNS}
          filename="crm_customers"
          title="导出客户数据"
          description="选择导出格式和列配置"
        />
      </div>

      {/* 客户视图 */}
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
        <div className="text-center py-16">
          <Users className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium">暂无客户</h3>
          <p className="text-muted-foreground mt-1">点击上方"新建客户"按钮添加第一个客户</p>
        </div>
      ) : viewMode === 'kanban' ? (
        <KanbanView customers={customers} onSelect={handleSelectCustomer} />
      ) : (
        <ListView customers={customers} onSelect={handleSelectCustomer} />
      )}

      {/* 客户详情侧边栏 */}
      <CustomerDetailSheet
        customer={selectedCustomer}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
      />

      {/* 新建客户弹窗 */}
      <CreateCustomerDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}

export default CRMPage;
