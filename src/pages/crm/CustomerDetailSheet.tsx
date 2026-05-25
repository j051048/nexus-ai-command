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
  Heart,
  AlertTriangle,
  ShieldCheck,
  Brain,
  ChevronDown,
  ChevronUp,
  Sparkles,
  FileCheck2,
  FileText,
  Goal,
  Handshake,
  LineChart,
  ListChecks,
  Swords,
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
  useCustomerHealth,
} from '@/hooks/useCRM';
import type { Customer, CustomerActivity, CustomerContact } from '@/hooks/useCRM';
import { toast } from 'sonner';
import { useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
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

function AIInsightsPanel({ customerName }: { customerName: string }) {
  const [expanded, setExpanded] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ['ai-customer-insights', customerName],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: {
        has_insights: boolean;
        summary: string;
        key_points: string[];
        sentiment?: string;
        suggested_action?: string;
        last_mentioned?: string;
        memory_count?: number;
      } }>(`api/ai/customer-memory-summary/${encodeURIComponent(customerName)}`);
      return res.data;
    },
    enabled: expanded,
    staleTime: 1000 * 60 * 10, // 10 min
  });

  const sentimentColors: Record<string, string> = {
    positive: 'text-green-500',
    neutral: 'text-muted-foreground',
    negative: 'text-red-500',
  };

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      <button
        className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-sm font-medium flex items-center gap-1.5">
          <Brain className="w-4 h-4 text-purple-500" />
          AI 洞察
        </span>
        {expanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>

      {expanded && (
        <div className="px-3 pb-3 border-t">
          {isLoading ? (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              正在分析客户记忆...
            </div>
          ) : !data?.has_insights ? (
            <p className="text-sm text-muted-foreground py-3">暂无 AI 洞察。与 AI 对话中提及此客户后将自动生成。</p>
          ) : (
            <div className="space-y-2 pt-2">
              <div className="flex items-start gap-2">
                <Sparkles className="w-3.5 h-3.5 text-purple-500 mt-0.5 shrink-0" />
                <p className="text-sm">{data.summary}</p>
              </div>
              {data.key_points && data.key_points.length > 0 && (
                <ul className="space-y-1 ml-5">
                  {data.key_points.map((point, i) => (
                    <li key={i} className="text-xs text-muted-foreground list-disc">{point}</li>
                  ))}
                </ul>
              )}
              {data.suggested_action && (
                <p className="text-xs text-purple-600 dark:text-purple-400 bg-purple-500/5 rounded px-2 py-1">
                  建议: {data.suggested_action}
                </p>
              )}
              <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1">
                {data.sentiment && (
                  <span className={sentimentColors[data.sentiment] || ''}>
                    情感: {data.sentiment === 'positive' ? '正面' : data.sentiment === 'negative' ? '负面' : '中性'}
                  </span>
                )}
                {data.memory_count && <span>基于 {data.memory_count} 条记忆</span>}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

function Customer360Panel({
  customer,
  contacts,
  timeline,
}: {
  customer: Customer;
  contacts: CustomerContact[];
  timeline: CustomerActivity[];
}) {
  const metadata = customer.metadata || {};
  const competitors = Array.isArray(metadata.competitors)
    ? metadata.competitors
    : ['Thermo Fisher', 'Agilent', 'Shimadzu'];
  const quoteStatus = String(metadata.quote_status || '待报价');
  const tenderStatus = String(metadata.tender_status || '未进入招投标');
  const nextAction = String(
    metadata.next_action || '确认预算、使用场景和关键决策人，补齐技术方案证据。',
  );
  const decisionRoles = [
    { label: '拍板人', value: metadata.decision_maker || contacts[0]?.name || '待确认' },
    { label: '技术影响人', value: metadata.technical_owner || contacts[1]?.name || '实验老师/平台负责人' },
    { label: '采购/财务', value: metadata.procurement_owner || '采购办/财务待确认' },
  ];
  const evidence = [
    { label: '联系人', value: `${contacts.length} 位` },
    { label: '跟进记录', value: `${timeline.length} 条` },
    { label: '商机金额', value: `¥${Number(customer.estimated_value || 0).toLocaleString()}` },
    { label: '当前阶段', value: STAGES[customer.stage]?.name || customer.stage || '未标记' },
  ];

  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-card p-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold">客户 360 作战视图</div>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              把联系人、决策链、竞品、报价、招投标、证据和下一步动作放在一个详情面板里。
            </p>
          </div>
          <Button
            size="sm"
            onClick={() =>
              triggerAI(`请基于客户 360 信息，为 ${customer.name} 生成下一步推进计划、风险点和需要补齐的证据。`)
            }
          >
            <Sparkles className="mr-2 h-4 w-4" />
            AI 推进计划
          </Button>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {evidence.map((item) => (
            <div key={item.label} className="rounded-lg border bg-background/60 p-2">
              <div className="text-[11px] text-muted-foreground">{item.label}</div>
              <div className="mt-1 text-sm font-semibold">{item.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-3">
        <div className="rounded-lg border p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <Handshake className="h-4 w-4 text-emerald-600" />
            决策链
          </div>
          <div className="space-y-2">
            {decisionRoles.map((role) => (
              <div key={role.label} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-muted-foreground">{role.label}</span>
                <span className="font-medium">{String(role.value)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg border p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <Swords className="h-4 w-4 text-cyan-600" />
              竞品态势
            </div>
            <div className="flex flex-wrap gap-2">
              {competitors.map((competitor: string) => (
                <Badge key={competitor} variant="outline">
                  {competitor}
                </Badge>
              ))}
            </div>
            <Button
              className="mt-3 w-full"
              size="sm"
              variant="outline"
              onClick={() => triggerAI(`请为 ${customer.name} 生成竞品战卡，重点对比 ${competitors.join('、')}。`)}
            >
              生成竞品战卡
            </Button>
          </div>

          <div className="rounded-lg border p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <FileCheck2 className="h-4 w-4 text-amber-600" />
              报价 / 招投标
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">报价</span>
                <span className="font-medium">{quoteStatus}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">招投标</span>
                <span className="font-medium">{tenderStatus}</span>
              </div>
            </div>
            <Button
              className="mt-3 w-full"
              size="sm"
              variant="outline"
              onClick={() => triggerAI(`请为 ${customer.name} 生成招投标评分拆解和报价风险清单。`)}
            >
              评估投标/报价风险
            </Button>
          </div>
        </div>

        <div className="rounded-lg border p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <ListChecks className="h-4 w-4 text-primary" />
            下一步动作
          </div>
          <p className="text-sm leading-6 text-muted-foreground">{nextAction}</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            {[
              { icon: FileText, label: '写跟进邮件' },
              { icon: Goal, label: '生成拜访提纲' },
              { icon: LineChart, label: '更新预测概率' },
            ].map((action) => {
              const Icon = action.icon;
              return (
                <Button
                  key={action.label}
                  size="sm"
                  variant="outline"
                  onClick={() => triggerAI(`请围绕客户 ${customer.name} ${action.label}。`)}
                >
                  <Icon className="mr-2 h-4 w-4" />
                  {action.label}
                </Button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CustomerDetailSheet({
  customer,
  open,
  onClose,
}: CustomerDetailSheetProps) {
  const { data: timeline = [], isLoading: timelineLoading } = useCustomerTimeline(customer?.id || null);
  const { data: contacts = [], isLoading: contactsLoading } = useCustomerContacts(customer?.id || null);
  const { data: health } = useCustomerHealth(customer?.id || null);
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
            <TabsList className="grid w-full grid-cols-4 mb-4">
              <TabsTrigger value="overview">概览</TabsTrigger>
              <TabsTrigger value="customer360">360</TabsTrigger>
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

              {/* Health Score */}
              {health && health.risk_level !== 'unknown' && (
                <div className="p-3 rounded-lg border bg-card">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium flex items-center gap-1.5">
                      <Heart className="w-4 h-4" />
                      健康度评分
                    </span>
                    <Badge
                      className={cn(
                        'text-xs',
                        health.risk_level === 'healthy' && 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
                        health.risk_level === 'at_risk' && 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
                        health.risk_level === 'churn_risk' && 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
                      )}
                    >
                      {health.risk_level === 'healthy' && <ShieldCheck className="w-3 h-3 mr-1" />}
                      {health.risk_level === 'at_risk' && <AlertTriangle className="w-3 h-3 mr-1" />}
                      {health.risk_level === 'churn_risk' && <AlertTriangle className="w-3 h-3 mr-1" />}
                      {health.risk_level === 'healthy' ? '健康' : health.risk_level === 'at_risk' ? '有风险' : '流失预警'}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-2xl font-bold">{health.health_score}</div>
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          health.risk_level === 'healthy' && 'bg-green-500',
                          health.risk_level === 'at_risk' && 'bg-amber-500',
                          health.risk_level === 'churn_risk' && 'bg-red-500',
                        )}
                        style={{ width: `${health.health_score}%` }}
                      />
                    </div>
                  </div>
                  {health.breakdown && (
                    <div className="grid grid-cols-5 gap-1 mt-2 text-[10px] text-muted-foreground">
                      <span>活跃度 {health.breakdown.activity_recency}</span>
                      <span>频率 {health.breakdown.activity_frequency}</span>
                      <span>联系人 {health.breakdown.contact_richness}</span>
                      <span>阶段 {health.breakdown.stage_progression}</span>
                      <span>价值 {health.breakdown.value_indicator}</span>
                    </div>
                  )}
                </div>
              )}

              {/* AI Insights Panel */}
              <AIInsightsPanel customerName={customer.name} />

              <Separator />

              <div className="text-xs text-muted-foreground">
                更新于 {new Date(customer.updated_at).toLocaleDateString('zh-CN')}
              </div>
            </TabsContent>

            <TabsContent value="customer360">
              <Customer360Panel
                customer={customer}
                contacts={contacts as CustomerContact[]}
                timeline={timeline as CustomerActivity[]}
              />
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
