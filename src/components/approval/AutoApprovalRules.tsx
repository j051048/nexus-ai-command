import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
import { useAuth } from '@/components/auth/AuthContext';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Loader2, Plus, Trash2, Shield } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';

interface AutoRule {
  id: string;
  name: string;
  approval_type: string;
  condition_field: string;
  condition_op: string;
  condition_value: number;
  is_active: boolean;
  created_at: string;
}

const OP_LABELS: Record<string, string> = {
  lte: '≤', lt: '<', gte: '≥', gt: '>', eq: '=',
};

const TYPE_LABELS: Record<string, string> = {
  expense: '费用报销', purchase: '采购申请', leave: '请假', default: '通用',
};

export function AutoApprovalRules() {
  const { profile } = useAuth();
  const isAdmin = profile?.role && ['boss', 'founder', 'super_admin'].includes(profile.role);

  const { data: rules = [], refetch, isLoading } = useQuery<AutoRule[]>({
    queryKey: ['auto-approval-rules'],
    queryFn: async () => {
      const res = await aiClient('/api/approval/auto-rules') as { data?: AutoRule[] };
      return res?.data || [];
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => aiClient(`/api/approval/auto-rules/${id}`, { method: 'DELETE' }),
    onSuccess: () => { toast.success('规则已删除'); refetch(); },
    onError: () => toast.error('删除失败'),
  });

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: '', approval_type: 'expense', condition_field: 'amount', condition_op: 'lte', condition_value: '',
  });

  const createMutation = useMutation({
    mutationFn: () => aiClient('/api/approval/auto-rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...form, condition_value: Number(form.condition_value) }),
    }),
    onSuccess: () => {
      toast.success('规则已创建');
      setOpen(false);
      setForm({ name: '', approval_type: 'expense', condition_field: 'amount', condition_op: 'lte', condition_value: '' });
      refetch();
    },
    onError: () => toast.error('创建失败'),
  });

  if (!isAdmin) return null;

  return (
    <div className="bg-card rounded-2xl p-6 border border-border space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-primary" />
          <h3 className="font-semibold text-lg">自动审批规则</h3>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm" variant="outline" className="gap-1">
              <Plus className="w-4 h-4" /> 新增规则
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>新增自动审批规则</DialogTitle></DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <Label>规则名称</Label>
                <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="如：小额报销自动通过" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>审批类型</Label>
                  <Select value={form.approval_type} onValueChange={v => setForm(f => ({ ...f, approval_type: v }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(TYPE_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>条件运算</Label>
                  <Select value={form.condition_op} onValueChange={v => setForm(f => ({ ...f, condition_op: v }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(OP_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label>阈值金额</Label>
                <Input type="number" value={form.condition_value} onChange={e => setForm(f => ({ ...f, condition_value: e.target.value }))} placeholder="500" />
              </div>
              <Button className="w-full" onClick={() => createMutation.mutate()} disabled={!form.name || !form.condition_value || createMutation.isPending}>
                {createMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                创建规则
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>
      ) : rules.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-4">暂无自动审批规则</p>
      ) : (
        <div className="space-y-2">
          {rules.map(rule => (
            <div key={rule.id} className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border">
              <div>
                <span className="font-medium text-sm">{rule.name}</span>
                <span className="text-xs text-muted-foreground ml-2">
                  {TYPE_LABELS[rule.approval_type] || rule.approval_type} · {rule.condition_field} {OP_LABELS[rule.condition_op] || rule.condition_op} {rule.condition_value}
                </span>
              </div>
              <Button
                size="icon" variant="ghost"
                onClick={() => deleteMutation.mutate(rule.id)}
                disabled={deleteMutation.isPending}
              >
                <Trash2 className="w-4 h-4 text-destructive" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
