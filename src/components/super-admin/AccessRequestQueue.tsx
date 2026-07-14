import { useEffect, useState } from 'react';
import { CalendarDays, Check, Clock3, Loader2, X } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import {
  type SubscriptionRequest,
  useDecideSubscriptionRequest,
} from '@/hooks/useSuperAdminConsole';

const PLAN_NAMES: Record<string, string> = {
  starter: '团队版',
  professional: '专业版',
  enterprise: '企业版',
};

function dateAfter(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

export function AccessRequestQueue({ requests, loading }: { requests: SubscriptionRequest[]; loading: boolean }) {
  const [selected, setSelected] = useState<SubscriptionRequest | null>(null);
  const [decision, setDecision] = useState<'approved' | 'rejected'>('approved');
  const [plan, setPlan] = useState('professional');
  const [expiresAt, setExpiresAt] = useState(dateAfter(365));
  const [reason, setReason] = useState('');
  const decideRequest = useDecideSubscriptionRequest();

  useEffect(() => {
    if (!selected) return;
    setPlan(selected.requested_plan);
    setExpiresAt(dateAfter(selected.requested_days));
    setReason('');
  }, [selected]);

  const openDecision = (request: SubscriptionRequest, nextDecision: 'approved' | 'rejected') => {
    setDecision(nextDecision);
    setSelected(request);
  };

  const submitDecision = async () => {
    if (!selected || reason.trim().length < 2) {
      toast.error('请填写审核说明');
      return;
    }
    try {
      await decideRequest.mutateAsync({
        requestId: selected.id,
        decision,
        reason: reason.trim(),
        plan: decision === 'approved' ? plan : undefined,
        expires_at:
          decision === 'approved' ? new Date(`${expiresAt}T23:59:59`).toISOString() : undefined,
      });
      toast.success(decision === 'approved' ? '会员已批准并即时生效' : '申请已拒绝');
      setSelected(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '审核操作失败');
    }
  };

  if (loading) {
    return <div className="flex min-h-40 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin" /></div>;
  }

  if (requests.length === 0) {
    return (
      <div className="flex min-h-48 flex-col items-center justify-center border-y text-center">
        <Check className="h-5 w-5 text-success" />
        <p className="mt-3 font-medium">会员申请已处理完毕</p>
        <p className="mt-1 text-sm text-muted-foreground">新的开通或续期申请会出现在这里。</p>
      </div>
    );
  }

  return (
    <>
      <div className="divide-y border-y">
        {requests.map((request) => (
          <article key={request.id} className="grid gap-4 py-4 lg:grid-cols-[1fr_170px_150px_auto] lg:items-center">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="truncate font-medium">{request.organization?.name ?? request.org_id}</h3>
                <Badge variant="outline">{PLAN_NAMES[request.requested_plan] ?? request.requested_plan}</Badge>
              </div>
              <p className="mt-1 line-clamp-1 text-sm text-muted-foreground">
                {request.note || '未填写用途说明'}
              </p>
            </div>
            <div className="text-sm">
              <p className="flex items-center gap-1.5"><CalendarDays className="h-3.5 w-3.5 text-muted-foreground" />申请 {request.requested_days} 天</p>
              <p className="mt-1 text-xs text-muted-foreground">{new Date(request.created_at).toLocaleString('zh-CN')}</p>
            </div>
            <div className="flex items-center gap-1.5 text-sm text-amber-700 dark:text-amber-300">
              <Clock3 className="h-3.5 w-3.5" />等待审核
            </div>
            <div className="flex gap-2 lg:justify-end">
              <Button size="sm" onClick={() => openDecision(request, 'approved')}><Check className="mr-1 h-4 w-4" />批准</Button>
              <Button size="sm" variant="outline" onClick={() => openDecision(request, 'rejected')}><X className="mr-1 h-4 w-4" />拒绝</Button>
            </div>
          </article>
        ))}
      </div>

      <Dialog open={Boolean(selected)} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{decision === 'approved' ? '批准会员申请' : '拒绝会员申请'}</DialogTitle>
            <DialogDescription>
              {selected?.organization?.name ?? selected?.org_id} · {selected && PLAN_NAMES[selected.requested_plan]}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {decision === 'approved' && (
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="approval-plan">生效套餐</Label>
                  <Select value={plan} onValueChange={setPlan}>
                    <SelectTrigger id="approval-plan"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="starter">团队版</SelectItem>
                      <SelectItem value="professional">专业版</SelectItem>
                      <SelectItem value="enterprise">企业版</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="approval-expiry">有效期至</Label>
                  <Input id="approval-expiry" type="date" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} />
                </div>
              </div>
            )}
            <div className="grid gap-2">
              <Label htmlFor="approval-reason">审核说明</Label>
              <Textarea
                id="approval-reason"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder={decision === 'approved' ? '例如：合同已确认，批准正式使用' : '说明未通过原因'}
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelected(null)}>取消</Button>
            <Button
              variant={decision === 'approved' ? 'default' : 'destructive'}
              onClick={submitDecision}
              disabled={decideRequest.isPending}
            >
              {decideRequest.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {decision === 'approved' ? '批准并生效' : '确认拒绝'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
