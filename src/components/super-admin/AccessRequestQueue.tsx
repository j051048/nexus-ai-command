import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CalendarDays, Check, Clock3, Loader2, X } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
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
  useBatchDecideSubscriptionRequests,
  useDecideSubscriptionRequest,
} from '@/hooks/useSuperAdminConsole';

const PLAN_NAMES: Record<string, string> = {
  starter: '团队版',
  professional: '专业版',
  enterprise: '企业版',
};

const PRIORITY_NAMES: Record<string, string> = {
  low: '低',
  normal: '普通',
  high: '高',
  urgent: '紧急',
};

function dateAfter(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function formatWait(seconds = 0): string {
  if (seconds < 3600) return `${Math.max(1, Math.floor(seconds / 60))} 分钟`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时`;
  return `${Math.floor(seconds / 86400)} 天`;
}

interface AccessRequestQueueProps {
  requests: SubscriptionRequest[];
  loading: boolean;
  onOpenOrganization?: (orgId: string) => void;
  canManage?: boolean;
}

export function AccessRequestQueue({
  requests,
  loading,
  onOpenOrganization,
  canManage = true,
}: AccessRequestQueueProps) {
  const [selected, setSelected] = useState<SubscriptionRequest | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [filter, setFilter] = useState<'all' | 'overdue' | 'urgent'>('all');
  const [decision, setDecision] = useState<'approved' | 'rejected'>('approved');
  const [batchOpen, setBatchOpen] = useState(false);
  const [plan, setPlan] = useState('professional');
  const [expiresAt, setExpiresAt] = useState(dateAfter(365));
  const [reason, setReason] = useState('');
  const decideRequest = useDecideSubscriptionRequest();
  const batchDecision = useBatchDecideSubscriptionRequests();

  const visibleRequests = useMemo(() => {
    if (filter === 'overdue') return requests.filter((item) => item.is_overdue);
    if (filter === 'urgent') return requests.filter((item) => item.priority === 'urgent');
    return requests;
  }, [filter, requests]);

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
        expires_at: decision === 'approved' ? new Date(`${expiresAt}T23:59:59`).toISOString() : undefined,
      });
      toast.success(decision === 'approved' ? '会员已批准并即时生效' : '申请已拒绝');
      setSelected(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '审核操作失败');
    }
  };

  const submitBatch = async () => {
    if (!selectedIds.length || reason.trim().length < 2) {
      toast.error('请选择申请并填写审核说明');
      return;
    }
    try {
      await batchDecision.mutateAsync({
        request_ids: selectedIds,
        decision,
        reason: reason.trim(),
        plan: decision === 'approved' ? plan : undefined,
        expires_at: decision === 'approved' ? new Date(`${expiresAt}T23:59:59`).toISOString() : undefined,
      });
      toast.success(`已提交 ${selectedIds.length} 项批量审核`);
      setSelectedIds([]);
      setBatchOpen(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '批量审核失败');
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
      <div className="flex flex-wrap items-center justify-between gap-3 border-y py-3">
        <div className="flex items-center gap-1">
          {(['all', 'overdue', 'urgent'] as const).map((value) => (
            <Button
              key={value}
              variant={filter === value ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setFilter(value)}
            >
              {value === 'all' ? `全部 ${requests.length}` : value === 'overdue' ? '已超时' : '紧急'}
            </Button>
          ))}
        </div>
        {canManage && selectedIds.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">已选 {selectedIds.length} 项</span>
            <Button size="sm" onClick={() => { setDecision('approved'); setReason(''); setBatchOpen(true); }}>批量批准</Button>
            <Button size="sm" variant="outline" onClick={() => { setDecision('rejected'); setReason(''); setBatchOpen(true); }}>批量拒绝</Button>
          </div>
        )}
      </div>

      <div className="divide-y">
        {visibleRequests.map((request) => (
          <article
            key={request.id}
            className={`grid gap-3 py-4 lg:items-center ${
              canManage
                ? 'lg:grid-cols-[28px_1fr_170px_150px_auto]'
                : 'lg:grid-cols-[1fr_170px_150px]'
            }`}
          >
            {canManage && (
              <Checkbox
                checked={selectedIds.includes(request.id)}
                aria-label={`选择 ${request.organization?.name ?? request.org_id}`}
                onCheckedChange={(checked) =>
                  setSelectedIds((current) => checked ? [...current, request.id] : current.filter((id) => id !== request.id))
                }
              />
            )}
            <button className="min-w-0 text-left" onClick={() => onOpenOrganization?.(request.org_id)}>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="truncate font-medium">{request.organization?.name ?? request.org_id}</h3>
                <Badge variant="outline">{PLAN_NAMES[request.requested_plan] ?? request.requested_plan}</Badge>
                {request.priority && request.priority !== 'normal' && (
                  <Badge variant={request.priority === 'urgent' ? 'destructive' : 'secondary'}>
                    {PRIORITY_NAMES[request.priority]}
                  </Badge>
                )}
              </div>
              <p className="mt-1 line-clamp-1 text-sm text-muted-foreground">{request.note || '未填写用途说明'}</p>
            </button>
            <div className="text-sm">
              <p className="flex items-center gap-1.5"><CalendarDays className="h-3.5 w-3.5 text-muted-foreground" />申请 {request.requested_days} 天</p>
              <p className="mt-1 text-xs text-muted-foreground">{new Date(request.created_at).toLocaleString('zh-CN')}</p>
            </div>
            <div className={`flex items-center gap-1.5 text-sm ${request.is_overdue ? 'text-destructive' : 'text-muted-foreground'}`}>
              {request.is_overdue ? <AlertTriangle className="h-3.5 w-3.5" /> : <Clock3 className="h-3.5 w-3.5" />}
              等待 {formatWait(request.waiting_seconds)}
            </div>
            {canManage && (
              <div className="flex gap-2 lg:justify-end">
                <Button size="sm" onClick={() => openDecision(request, 'approved')}><Check className="mr-1 h-4 w-4" />批准</Button>
                <Button size="sm" variant="outline" onClick={() => openDecision(request, 'rejected')}><X className="mr-1 h-4 w-4" />拒绝</Button>
              </div>
            )}
          </article>
        ))}
      </div>

      <DecisionDialog
        open={Boolean(selected)}
        title={decision === 'approved' ? '批准会员申请' : '拒绝会员申请'}
        description={selected ? `${selected.organization?.name ?? selected.org_id} · ${PLAN_NAMES[selected.requested_plan]}` : ''}
        decision={decision}
        plan={plan}
        expiresAt={expiresAt}
        reason={reason}
        pending={decideRequest.isPending}
        onPlanChange={setPlan}
        onExpiryChange={setExpiresAt}
        onReasonChange={setReason}
        onClose={() => setSelected(null)}
        onSubmit={submitDecision}
      />
      <DecisionDialog
        open={batchOpen}
        title={`批量${decision === 'approved' ? '批准' : '拒绝'} ${selectedIds.length} 项申请`}
        description="批量批准时将使用统一套餐和有效期，请确认所选企业适用相同条件。"
        decision={decision}
        plan={plan}
        expiresAt={expiresAt}
        reason={reason}
        pending={batchDecision.isPending}
        onPlanChange={setPlan}
        onExpiryChange={setExpiresAt}
        onReasonChange={setReason}
        onClose={() => setBatchOpen(false)}
        onSubmit={submitBatch}
      />
    </>
  );
}

interface DecisionDialogProps {
  open: boolean;
  title: string;
  description: string;
  decision: 'approved' | 'rejected';
  plan: string;
  expiresAt: string;
  reason: string;
  pending: boolean;
  onPlanChange: (value: string) => void;
  onExpiryChange: (value: string) => void;
  onReasonChange: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}

function DecisionDialog(props: DecisionDialogProps) {
  return (
    <Dialog open={props.open} onOpenChange={(open) => !open && props.onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader><DialogTitle>{props.title}</DialogTitle><DialogDescription>{props.description}</DialogDescription></DialogHeader>
        <div className="space-y-4 py-2">
          {props.decision === 'approved' && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="approval-plan">生效套餐</Label>
                <Select value={props.plan} onValueChange={props.onPlanChange}>
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
                <Input id="approval-expiry" type="date" value={props.expiresAt} onChange={(event) => props.onExpiryChange(event.target.value)} />
              </div>
            </div>
          )}
          <div className="grid gap-2">
            <Label htmlFor="approval-reason">审核说明</Label>
            <Textarea id="approval-reason" value={props.reason} onChange={(event) => props.onReasonChange(event.target.value)} rows={4} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={props.onClose}>取消</Button>
          <Button variant={props.decision === 'approved' ? 'default' : 'destructive'} onClick={props.onSubmit} disabled={props.pending}>
            {props.pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {props.decision === 'approved' ? '确认批准' : '确认拒绝'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
