import React, { useState, useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import {
  Plus,
  Building2,
  Phone,
  Mail,
  User2,
  MessageSquare,
  Clock,
  Pencil,
  Trash2,
  Loader2,
  Tag,
} from 'lucide-react';
import {
  useCustomerTimeline,
  useCustomerContacts,
  useUpdateCustomer,
  useDeleteCustomer,
  useCreateContact,
  useCreateActivity,
  useUpdateContact,
  useDeleteContact,
} from '@/hooks/useCRM';
import type { Customer, CustomerActivity, CustomerContact } from '@/hooks/useCRM';
import { toast } from 'sonner';
import { STAGES, ACTIVITY_ICONS, ACTIVITY_NAMES } from './constants';

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
  const { confirm, ConfirmDialog } = useConfirmDialog();

  const handleDelete = async () => {
    if (!(await confirm(`确认删除联系人「${contact.name}」？`))) return;
    deleteContact.mutate(contact.id);
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
      {ConfirmDialog}
    </div>
  );
}

export function EditCustomerDialog({
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

export interface CustomerDetailSheetProps {
  customer: Customer | null;
  open: boolean;
  onClose: () => void;
}

export default function CustomerDetailSheet({
  customer,
  open,
  onClose,
}: CustomerDetailSheetProps) {
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

  const filteredTimeline = activityFilter === 'all'
    ? (timeline as CustomerActivity[])
    : (timeline as CustomerActivity[]).filter(a => a.activity_type === activityFilter);

  const timelineRef = useRef<HTMLDivElement>(null);
  const timelineVirtualizer = useVirtualizer({
    count: filteredTimeline.length,
    getScrollElement: () => timelineRef.current,
    estimateSize: () => 80,
    overscan: 5,
  });

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
                时间线 {filteredTimeline.length > 0 && `(${filteredTimeline.length})`}
              </TabsTrigger>
            </TabsList>

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

            <TabsContent value="timeline" className="space-y-3">
              <div className="flex items-center justify-between gap-2">
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
                <div 
                  ref={timelineRef}
                  className="h-[500px] overflow-auto pr-2 custom-scrollbar-minimal"
                  style={{ contain: 'strict' }}
                >
                  <div
                    style={{
                      height: `${timelineVirtualizer.getTotalSize()}px`,
                      width: '100%',
                      position: 'relative',
                    }}
                  >
                    {timelineVirtualizer.getVirtualItems().map((virtualRow) => {
                      const act = filteredTimeline[virtualRow.index];
                      return (
                        <div
                          key={virtualRow.key}
                          data-index={virtualRow.index}
                          ref={timelineVirtualizer.measureElement}
                          style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            width: '100%',
                            transform: `translateY(${virtualRow.start}px)`,
                          }}
                          className="flex gap-3 pb-4"
                        >
                          <div className="mt-1 p-2 rounded-full bg-muted/60 shrink-0 border">
                            {ACTIVITY_ICONS[act.activity_type] || <MessageSquare className="w-4 h-4" />}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-semibold">{ACTIVITY_NAMES[act.activity_type] || act.activity_type}</span>
                              <span className="text-[10px] text-muted-foreground font-medium uppercase">
                                {new Date(act.created_at).toLocaleDateString('zh-CN')}
                              </span>
                            </div>
                            <p className="text-sm text-muted-foreground leading-snug mt-1">{act.content}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </SheetContent>
      </Sheet>

      <EditCustomerDialog customer={customer} open={editOpen} onClose={() => setEditOpen(false)} />

      <AddContactDialog customerId={customer.id} open={addContactOpen} onClose={() => setAddContactOpen(false)} />

      <EditContactDialog
        customerId={customer.id}
        contact={editingContact}
        open={!!editingContact}
        onClose={() => setEditingContact(null)}
      />

      <AddActivityDialog customerId={customer.id} open={addActivityOpen} onClose={() => setAddActivityOpen(false)} />

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
