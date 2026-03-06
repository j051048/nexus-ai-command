import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  ClipboardList,
  Plus,
  Loader2,
  Search,
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Wrench,
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface WorkOrder {
  id: string;
  title: string;
  order_type: string;
  priority: string;
  status: string;
  description?: string;
  assignee_name?: string;
  created_at: string;
}

type KanbanColumn = 'open' | 'processing' | 'resolved' | 'closed';

const COLUMNS: { key: KanbanColumn; label: string; color: string; icon: React.ElementType }[] = [
  { key: 'open', label: '待处理', color: 'bg-blue-500', icon: Clock },
  { key: 'processing', label: '处理中', color: 'bg-amber-500', icon: Wrench },
  { key: 'resolved', label: '已解决', color: 'bg-green-500', icon: CheckCircle2 },
  { key: 'closed', label: '已关闭', color: 'bg-gray-400', icon: XCircle },
];

const PRIORITY_MAP: Record<string, { label: string; variant: 'destructive' | 'default' | 'secondary' | 'outline' }> = {
  urgent: { label: '紧急', variant: 'destructive' },
  high: { label: '高', variant: 'destructive' },
  medium: { label: '中', variant: 'default' },
  low: { label: '低', variant: 'secondary' },
};

const TYPE_MAP: Record<string, string> = {
  repair: '报修',
  complaint: '投诉',
  request: '申请',
  it_support: 'IT支持',
  other: '其他',
};

export default function WorkOrderPage() {
  const { profile } = useAuth();
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    title: '',
    order_type: 'repair',
    priority: 'medium',
    description: '',
  });

  const orgId = profile?.organization_id;

  const fetchOrders = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      let query = supabase
        .from('work_orders')
        .select('id, title, order_type, priority, status, description, created_at')
        .eq('organization_id', orgId)
        .order('created_at', { ascending: false });

      if (filterType !== 'all') {
        query = query.eq('order_type', filterType);
      }
      if (search.trim()) {
        query = query.ilike('title', `%${search.trim()}%`);
      }

      const { data, error } = await query;
      if (error) throw error;
      setOrders((data as WorkOrder[]) || []);
    } catch (e) {
      toast.error('加载工单失败: ' + (e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [orgId, filterType, search]);

  useEffect(() => { fetchOrders(); }, [fetchOrders]);

  const handleCreate = async () => {
    if (!form.title.trim()) { toast.error('请填写工单标题'); return; }
    setSubmitting(true);
    try {
      // @ts-expect-error Types not fully generated
      const { error } = await supabase.from('work_orders').insert({
        title: form.title.trim(),
        order_type: form.order_type,
        priority: form.priority,
        description: form.description.trim() || null,
        status: 'open',
        organization_id: orgId,
        creator_id: profile?.id,
      });
      if (error) throw error;
      toast.success('工单创建成功');
      setDialogOpen(false);
      setForm({ title: '', order_type: 'repair', priority: 'medium', description: '' });
      fetchOrders();
    } catch (e) {
      toast.error('创建失败: ' + (e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const grouped = COLUMNS.reduce<Record<KanbanColumn, WorkOrder[]>>(
    (acc, col) => {
      acc[col.key] = orders.filter((o) => o.status === col.key);
      return acc;
    },
    { open: [], processing: [], resolved: [], closed: [] },
  );

  const stats = {
    total: orders.length,
    open: grouped.open.length,
    processing: grouped.processing.length,
    resolved: grouped.resolved.length,
  };

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ClipboardList className="h-6 w-6" /> 工单管理
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            创建、分配和跟踪工单流转
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" /> 新建工单
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: '全部工单', value: stats.total, color: 'text-foreground' },
          { label: '待处理', value: stats.open, color: 'text-blue-500' },
          { label: '处理中', value: stats.processing, color: 'text-amber-500' },
          { label: '已解决', value: stats.resolved, color: 'text-green-500' },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="pt-4 pb-3 px-4">
              <p className="text-sm text-muted-foreground">{s.label}</p>
              <p className={cn('text-2xl font-bold', s.color)}>{s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="搜索工单..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={filterType} onValueChange={setFilterType}>
          <SelectTrigger className="w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部类型</SelectItem>
            {Object.entries(TYPE_MAP).map(([k, v]) => (
              <SelectItem key={k} value={k}>{v}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Kanban Board */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {COLUMNS.map((col) => {
            const Icon = col.icon;
            const items = grouped[col.key];
            return (
              <div key={col.key} className="space-y-3">
                <div className="flex items-center gap-2 px-1">
                  <span className={cn('w-2.5 h-2.5 rounded-full', col.color)} />
                  <h3 className="text-sm font-semibold">{col.label}</h3>
                  <Badge variant="secondary" className="ml-auto text-xs">{items.length}</Badge>
                </div>
                <div className="space-y-2 min-h-[120px]">
                  {items.length === 0 ? (
                    <div className="text-center text-xs text-muted-foreground py-8 border border-dashed rounded-lg">
                      暂无工单
                    </div>
                  ) : (
                    items.map((order) => {
                      const pri = PRIORITY_MAP[order.priority] || PRIORITY_MAP.medium;
                      return (
                        <Card key={order.id} className="hover:shadow-md transition-shadow cursor-pointer">
                          <CardContent className="p-3 space-y-2">
                            <div className="flex items-start justify-between gap-2">
                              <p className="text-sm font-medium leading-tight line-clamp-2">{order.title}</p>
                              <Badge variant={pri.variant} className="shrink-0 text-[10px]">{pri.label}</Badge>
                            </div>
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <span>{TYPE_MAP[order.order_type] || order.order_type}</span>
                              <span>&middot;</span>
                              <span>{new Date(order.created_at).toLocaleDateString('zh-CN')}</span>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>新建工单</DialogTitle>
            <DialogDescription>填写工单信息后提交</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>标题 *</Label>
              <Input
                placeholder="简要描述问题..."
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                maxLength={200}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>类型</Label>
                <Select value={form.order_type} onValueChange={(v) => setForm({ ...form, order_type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(TYPE_MAP).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>优先级</Label>
                <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">低</SelectItem>
                    <SelectItem value="medium">中</SelectItem>
                    <SelectItem value="high">高</SelectItem>
                    <SelectItem value="urgent">紧急</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label>描述</Label>
              <Textarea
                placeholder="详细描述问题..."
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                maxLength={2000}
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
            <Button onClick={handleCreate} disabled={submitting}>
              {submitting && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              提交工单
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
