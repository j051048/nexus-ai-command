/**
 * CRM 客户关系管理页面
 * 看板/列表视图、客户详情侧边栏、新建编辑弹窗、搜索筛选
 */

import React, { useState, useMemo } from 'react';
import { useDebounce } from '@/hooks/useDebounce';
import { NoDataYet, NoSearchResults } from '@/components/common/EmptyState';
import { Card, CardContent } from '@/components/ui/card';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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
  User2,
  DollarSign,
  MessageSquare,
  Clock,
  ArrowRightLeft,
  Pencil,
  Trash2,
  Loader2,
  MoreHorizontal,
  Eye,
  Tag,
} from 'lucide-react';
import {
  useCustomers,
  useCustomerTimeline,
  useCustomerContacts,
  useCreateCustomer,
  useCustomerStats,
  useUpdateCustomer,
  useDeleteCustomer,
  useCreateContact,
  useCreateActivity,
  useUpdateContact,
  useDeleteContact,
} from '@/hooks/useCRM';
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
  const updateMutation = useUpdateCustomer();

  const handleStageChange = (e: React.MouseEvent, customer: Customer, newStage: string) => {
    e.stopPropagation();
    if (newStage !== customer.stage) {
      updateMutation.mutate({ id: customer.id, data: { stage: newStage } });
    }
  };

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
                <div key={c.id} className="relative group">
                  <CustomerCard customer={c} onClick={() => onSelect(c)} />
                  <div className="absolute bottom-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity" onClick={e => e.stopPropagation()}>
                    <Select value={c.stage} onValueChange={(v) => handleStageChange({ stopPropagation: () => {} } as React.MouseEvent, c, v)}>
                      <SelectTrigger className="h-6 w-[80px] text-xs bg-background/90 backdrop-blur-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(STAGES).filter(([k]) => k !== 'churned').map(([key, val]) => (
                          <SelectItem key={key} value={key} className="text-xs">{val.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
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
  onEdit,
  onDelete,
}: {
  customers: Customer[];
  onSelect: (c: Customer) => void;
  onEdit: (c: Customer) => void;
  onDelete: (c: Customer) => void;
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
            <div className="col-span-1 md:col-span-1 lg:col-span-1" onClick={e => e.stopPropagation()}>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                    <MoreHorizontal className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => onSelect(c)}>
                    <Eye className="w-4 h-4 mr-2" />
                    查看详情
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onEdit(c)}>
                    <Pencil className="w-4 h-4 mr-2" />
                    编辑
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem className="text-destructive" onClick={() => onDelete(c)}>
                    <Trash2 className="w-4 h-4 mr-2" />
                    删除
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
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
  const updateMutation = useUpdateCustomer();
  const deleteMutation = useDeleteCustomer();

  const [editOpen, setEditOpen] = useState(false);
  const [addContactOpen, setAddContactOpen] = useState(false);
  const [addActivityOpen, setAddActivityOpen] = useState(false);
  const [editingContact, setEditingContact] = useState<CustomerContact | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [activityFilter, setActivityFilter] = useState<string>('all');

  if (!customer) return null;

  const stage = STAGES[customer.stage] || STAGES.lead;

  const handleStageChange = (newStage: string) => {
    updateMutation.mutate({ id: customer.id, data: { stage: newStage } });
  };

  const handleDeleteCustomer = async () => {
    try {
      await deleteMutation.mutateAsync(customer.id);
      setDeleteConfirmOpen(false);
      onClose();
    } catch {
      // error toast handled in hook
    }
  };

  const filteredTimeline = activityFilter === 'all'
    ? (timeline as CustomerActivity[])
    : (timeline as CustomerActivity[]).filter(a => a.activity_type === activityFilter);

  return (
    <>
      <Sheet open={open} onOpenChange={onClose}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          <SheetHeader className="mb-4">
            <div className="flex items-center justify-between">
              <SheetTitle className="flex items-center gap-2">
                <Building2 className="w-5 h-5" />
                {customer.name}
              </SheetTitle>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" onClick={() => setEditOpen(true)}>
                  <Pencil className="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteConfirmOpen(true)}>
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
            <SheetDescription>{customer.company}</SheetDescription>
          </SheetHeader>

          <Tabs defaultValue="overview" className="w-full">
            <TabsList className="grid w-full grid-cols-3 mb-4">
              <TabsTrigger value="overview">概览</TabsTrigger>
              <TabsTrigger value="contacts">
                联系人 {(contacts as CustomerContact[]).length > 0 && `(${(contacts as CustomerContact[]).length})`}
              </TabsTrigger>
              <TabsTrigger value="timeline">
                时间线 {(timeline as CustomerActivity[]).length > 0 && `(${(timeline as CustomerActivity[]).length})`}
              </TabsTrigger>
            </TabsList>

            {/* 概览 Tab */}
            <TabsContent value="overview" className="space-y-4">
              <div className="flex items-center justify-between">
                <Select value={customer.stage} onValueChange={handleStageChange}>
                  <SelectTrigger className="w-[130px]">
                    <Badge className={cn('text-sm', stage.color, stage.bg)}>{stage.name}</Badge>
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(STAGES).map(([key, val]) => (
                      <SelectItem key={key} value={key}>{val.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
                  <span className="text-muted-foreground">负责人</span>
                  <p className="font-medium">{customer.assigned_to || '未分配'}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">创建时间</span>
                  <p className="font-medium">{new Date(customer.created_at).toLocaleDateString('zh-CN')}</p>
                </div>
              </div>

              {/* 标签 */}
              {customer.tags && customer.tags.length > 0 && (
                <div>
                  <span className="text-sm text-muted-foreground">标签</span>
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {customer.tags.map((tag, i) => (
                      <Badge key={i} variant="outline" className="text-xs gap-1">
                        <Tag className="w-3 h-3" />
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              <Separator />

              <div className="text-xs text-muted-foreground">
                更新于 {new Date(customer.updated_at).toLocaleDateString('zh-CN')}
              </div>
            </TabsContent>

            {/* 联系人 Tab */}
            <TabsContent value="contacts" className="space-y-3">
              <div className="flex items-center justify-end">
                <Button variant="outline" size="sm" className="gap-1 h-7 text-xs" onClick={() => setAddContactOpen(true)}>
                  <Plus className="w-3 h-3" />
                  添加联系人
                </Button>
              </div>
              {contactsLoading ? (
                <Skeleton className="h-16 w-full" />
              ) : (contacts as CustomerContact[]).length === 0 ? (
                <div className="text-center py-8 text-sm text-muted-foreground">
                  <User2 className="w-8 h-8 mx-auto mb-2 opacity-40" />
                  暂无联系人
                </div>
              ) : (
                <div className="space-y-2">
                  {(contacts as CustomerContact[]).map(contact => (
                    <ContactRow
                      key={contact.id}
                      contact={contact}
                      customerId={customer.id}
                      onEdit={() => setEditingContact(contact)}
                    />
                  ))}
                </div>
              )}
            </TabsContent>

            {/* 时间线 Tab */}
            <TabsContent value="timeline" className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                {/* 活动类型筛选 */}
                <div className="flex flex-wrap gap-1">
                  <Badge
                    variant={activityFilter === 'all' ? 'default' : 'outline'}
                    className="cursor-pointer text-xs"
                    onClick={() => setActivityFilter('all')}
                  >
                    全部
                  </Badge>
                  {Object.entries(ACTIVITY_NAMES).map(([key, name]) => (
                    <Badge
                      key={key}
                      variant={activityFilter === key ? 'default' : 'outline'}
                      className="cursor-pointer text-xs"
                      onClick={() => setActivityFilter(key)}
                    >
                      {name}
                    </Badge>
                  ))}
                </div>
                <Button variant="outline" size="sm" className="gap-1 h-7 text-xs shrink-0" onClick={() => setAddActivityOpen(true)}>
                  <Plus className="w-3 h-3" />
                  添加跟进
                </Button>
              </div>
              {timelineLoading ? (
                <div className="space-y-2">{[1, 2, 3].map(i => <Skeleton key={i} className="h-12 w-full" />)}</div>
              ) : filteredTimeline.length === 0 ? (
                <div className="text-center py-8 text-sm text-muted-foreground">
                  <Clock className="w-8 h-8 mx-auto mb-2 opacity-40" />
                  {activityFilter === 'all' ? '暂无活动记录' : `暂无${ACTIVITY_NAMES[activityFilter]}记录`}
                </div>
              ) : (
                <ScrollArea className="h-[400px]">
                  <div className="space-y-3">
                    {filteredTimeline.map(act => (
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
            </TabsContent>
          </Tabs>
        </SheetContent>
      </Sheet>

      {/* Edit Customer Dialog */}
      <EditCustomerDialog customer={customer} open={editOpen} onClose={() => setEditOpen(false)} />

      {/* Add Contact Dialog */}
      <AddContactDialog customerId={customer.id} open={addContactOpen} onClose={() => setAddContactOpen(false)} />

      {/* Edit Contact Dialog */}
      <EditContactDialog
        customerId={customer.id}
        contact={editingContact}
        open={!!editingContact}
        onClose={() => setEditingContact(null)}
      />

      {/* Add Activity Dialog */}
      <AddActivityDialog customerId={customer.id} open={addActivityOpen} onClose={() => setAddActivityOpen(false)} />

      {/* Delete Customer Confirmation */}
      <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="w-5 h-5" />
              确认删除客户
            </DialogTitle>
            <DialogDescription>
              您即将删除客户 <strong>{customer.name}</strong>。此操作将同时删除该客户的所有联系人和活动记录，且不可撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirmOpen(false)}>取消</Button>
            <Button variant="destructive" onClick={handleDeleteCustomer} disabled={deleteMutation.isPending}>
              {deleteMutation.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              确认删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ────────────────── Contact Row (with edit/delete) ────────────────── */
function ContactRow({
  contact,
  customerId,
  onEdit,
}: {
  contact: CustomerContact;
  customerId: string;
  onEdit: () => void;
}) {
  const deleteContact = useDeleteContact(customerId);

  const handleDelete = () => {
    if (window.confirm(`确认删除联系人「${contact.name}」？`)) {
      deleteContact.mutate(contact.id);
    }
  };

  return (
    <div className="flex items-center justify-between p-2 rounded-lg border group">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{contact.name}</span>
          {contact.is_primary && <Badge variant="secondary" className="text-xs">主要</Badge>}
        </div>
        <p className="text-xs text-muted-foreground">{contact.title}</p>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {contact.phone && (
            <a href={`tel:${contact.phone}`} className="flex items-center gap-1 hover:text-foreground hover:underline" onClick={e => e.stopPropagation()}>
              <Phone className="w-3 h-3" />{contact.phone}
            </a>
          )}
          {contact.email && (
            <a href={`mailto:${contact.email}`} className="flex items-center gap-1 hover:text-foreground hover:underline" onClick={e => e.stopPropagation()}>
              <Mail className="w-3 h-3" />{contact.email}
            </a>
          )}
        </div>
        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={onEdit}>
            <Pencil className="w-3 h-3" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 text-destructive hover:text-destructive"
            onClick={handleDelete}
            disabled={deleteContact.isPending}
          >
            <Trash2 className="w-3 h-3" />
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ────────────────── Edit Customer Dialog ────────────────── */
function EditCustomerDialog({
  customer,
  open,
  onClose,
}: {
  customer: Customer;
  open: boolean;
  onClose: () => void;
}) {
  const updateMutation = useUpdateCustomer();
  const [form, setForm] = useState({
    name: '',
    company: '',
    industry: '',
    stage: 'lead',
    source: '',
    estimated_value: '',
    tags: '' as string,
  });

  // Sync form when dialog opens or customer changes
  React.useEffect(() => {
    if (open && customer) {
      setForm({
        name: customer.name || '',
        company: customer.company || '',
        industry: customer.industry || '',
        stage: customer.stage || 'lead',
        source: customer.source || '',
        estimated_value: customer.estimated_value ? String(customer.estimated_value) : '',
        tags: (customer.tags || []).join(', '),
      });
    }
  }, [open, customer]);

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      toast.error('请输入客户名称');
      return;
    }
    const tagsArray = form.tags
      .split(/[,，]/)
      .map(t => t.trim())
      .filter(Boolean);
    try {
      await updateMutation.mutateAsync({
        id: customer.id,
        data: {
          name: form.name,
          company: form.company,
          industry: form.industry,
          stage: form.stage,
          source: form.source,
          estimated_value: form.estimated_value ? Number(form.estimated_value) : 0,
          tags: tagsArray,
        },
      });
      onClose();
    } catch {
      // error toast handled in hook
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>编辑客户</DialogTitle>
          <DialogDescription>修改客户基本信息</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>客户名称 *</Label>
            <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="项目或客户名称" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>公司</Label>
              <Input value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} placeholder="公司名称" />
            </div>
            <div className="space-y-2">
              <Label>行业</Label>
              <Input value={form.industry} onChange={e => setForm({ ...form, industry: e.target.value })} placeholder="行业领域" />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
              <Select value={form.source || '__none'} onValueChange={v => setForm({ ...form, source: v === '__none' ? '' : v })}>
                <SelectTrigger><SelectValue placeholder="选择来源" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">无</SelectItem>
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
          <div className="space-y-2">
            <Label>标签</Label>
            <Input value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })} placeholder="多个标签用逗号分隔，如：重点客户, VIP" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={updateMutation.isPending}>
            {updateMutation.isPending ? '保存中...' : '保存'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ────────────────── Add Contact Dialog ────────────────── */
function AddContactDialog({
  customerId,
  open,
  onClose,
}: {
  customerId: string;
  open: boolean;
  onClose: () => void;
}) {
  const createContact = useCreateContact(customerId);
  const [form, setForm] = useState({ name: '', title: '', phone: '', email: '', is_primary: false });

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      toast.error('请输入联系人姓名');
      return;
    }
    try {
      await createContact.mutateAsync(form);
      setForm({ name: '', title: '', phone: '', email: '', is_primary: false });
      onClose();
    } catch {
      // error toast handled in hook
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>添加联系人</DialogTitle>
          <DialogDescription>为客户添加新的联系人</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>姓名 *</Label>
            <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="联系人姓名" />
          </div>
          <div className="space-y-2">
            <Label>职位</Label>
            <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="如：技术总监" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>电话</Label>
              <Input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="手机或座机" />
            </div>
            <div className="space-y-2">
              <Label>邮箱</Label>
              <Input value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder="email@example.com" />
            </div>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_primary}
              onChange={e => setForm({ ...form, is_primary: e.target.checked })}
              className="rounded border-border"
            />
            <span className="text-sm">设为主要联系人</span>
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={createContact.isPending}>
            {createContact.isPending ? '添加中...' : '添加'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ────────────────── Edit Contact Dialog ────────────────── */
function EditContactDialog({
  customerId,
  contact,
  open,
  onClose,
}: {
  customerId: string;
  contact: CustomerContact | null;
  open: boolean;
  onClose: () => void;
}) {
  const updateContact = useUpdateContact(customerId);
  const [form, setForm] = useState({ name: '', title: '', phone: '', email: '', is_primary: false });

  React.useEffect(() => {
    if (open && contact) {
      setForm({
        name: contact.name || '',
        title: contact.title || '',
        phone: contact.phone || '',
        email: contact.email || '',
        is_primary: contact.is_primary || false,
      });
    }
  }, [open, contact]);

  const handleSubmit = async () => {
    if (!contact) return;
    if (!form.name.trim()) {
      toast.error('请输入联系人姓名');
      return;
    }
    try {
      await updateContact.mutateAsync({ contactId: contact.id, data: form });
      onClose();
    } catch {
      // error toast handled in hook
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>编辑联系人</DialogTitle>
          <DialogDescription>修改联系人信息</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>姓名 *</Label>
            <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="联系人姓名" />
          </div>
          <div className="space-y-2">
            <Label>职位</Label>
            <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="如：技术总监" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>电话</Label>
              <Input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="手机或座机" />
            </div>
            <div className="space-y-2">
              <Label>邮箱</Label>
              <Input value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder="email@example.com" />
            </div>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_primary}
              onChange={e => setForm({ ...form, is_primary: e.target.checked })}
              className="rounded border-border"
            />
            <span className="text-sm">设为主要联系人</span>
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={updateContact.isPending}>
            {updateContact.isPending ? '保存中...' : '保存'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ────────────────── Add Activity Dialog ────────────────── */
function AddActivityDialog({
  customerId,
  open,
  onClose,
}: {
  customerId: string;
  open: boolean;
  onClose: () => void;
}) {
  const createActivity = useCreateActivity(customerId);
  const [form, setForm] = useState({ activity_type: 'call', content: '' });

  const handleSubmit = async () => {
    if (!form.content.trim()) {
      toast.error('请输入跟进内容');
      return;
    }
    try {
      await createActivity.mutateAsync(form);
      setForm({ activity_type: 'call', content: '' });
      onClose();
    } catch {
      // error toast handled in hook
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>添加跟进记录</DialogTitle>
          <DialogDescription>记录客户跟进活动</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>活动类型</Label>
            <Select value={form.activity_type} onValueChange={v => setForm({ ...form, activity_type: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {Object.entries(ACTIVITY_NAMES).map(([key, name]) => (
                  <SelectItem key={key} value={key}>{name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>跟进内容 *</Label>
            <Textarea
              value={form.content}
              onChange={e => setForm({ ...form, content: e.target.value })}
              placeholder="记录本次跟进的详细内容..."
              rows={4}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={createActivity.isPending}>
            {createActivity.isPending ? '添加中...' : '添加'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
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
      setForm({ name: '', company: '', industry: '', stage: 'lead', source: '', estimated_value: '' });
      onClose();
    } catch {
      // error toast handled in hook
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
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>公司</Label>
              <Input value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} placeholder="公司名称" />
            </div>
            <div className="space-y-2">
              <Label>行业</Label>
              <Input value={form.industry} onChange={e => setForm({ ...form, industry: e.target.value })} placeholder="行业领域" />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
        debouncedSearch ? (
          <NoSearchResults query={searchQuery} onClear={() => setSearchQuery('')} />
        ) : (
          <NoDataYet resourceName="客户" onAdd={() => setCreateOpen(true)} />
        )
      ) : viewMode === 'kanban' ? (
        <KanbanView customers={customers} onSelect={handleSelectCustomer} />
      ) : (
        <ListView
          customers={customers}
          onSelect={handleSelectCustomer}
          onEdit={(c) => setEditFromList(c)}
          onDelete={(c) => setDeleteFromList(c)}
        />
      )}

      {/* 客户详情侧边栏 */}
      <CustomerDetailSheet
        customer={selectedCustomer}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
      />

      {/* 新建客户弹窗 */}
      <CreateCustomerDialog open={createOpen} onClose={() => setCreateOpen(false)} />

      {/* 列表视图编辑弹窗 */}
      {editFromList && (
        <EditCustomerDialog customer={editFromList} open={!!editFromList} onClose={() => setEditFromList(null)} />
      )}

      {/* 列表视图删除确认 */}
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
