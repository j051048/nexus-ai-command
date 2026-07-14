import { useMemo, useState } from 'react';
import { AlertTriangle, CalendarDays, Check, Clock3, Loader2, Send, ShieldCheck } from 'lucide-react';
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
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import {
  type BillingPlan,
  useLatestAccessRequest,
  usePlans,
  useRequestAccess,
  useSubscription,
  useUsageStats,
} from '@/hooks/useBilling';
import { cn } from '@/lib/utils';

const PLAN_NAMES: Record<string, string> = {
  free: '基础版',
  starter: '团队版',
  professional: '专业版',
  enterprise: '企业版',
};

const REQUEST_STATUS: Record<string, string> = {
  pending: '审核中',
  approved: '已批准',
  rejected: '未通过',
  cancelled: '已取消',
};

function planId(plan: BillingPlan): string {
  return plan.plan ?? plan.id ?? 'professional';
}

function BillingDashboard() {
  const { data: plans, isLoading: plansLoading } = usePlans();
  const { data: subscription, isLoading: subscriptionLoading } = useSubscription();
  const { data: accessRequest } = useLatestAccessRequest();
  const { data: usage } = useUsageStats();
  const requestAccess = useRequestAccess();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [requestedPlan, setRequestedPlan] = useState('professional');
  const [requestedDays, setRequestedDays] = useState('365');
  const [note, setNote] = useState('');

  const expiresInDays = useMemo(() => {
    if (!subscription?.current_period_end) return null;
    const difference = new Date(subscription.current_period_end).getTime() - Date.now();
    return Math.ceil(difference / 86_400_000);
  }, [subscription?.current_period_end]);

  const hasActiveAccess = Boolean(subscription?.has_paid_access);
  const pendingRequest = accessRequest?.status === 'pending';

  const submitRequest = async () => {
    try {
      await requestAccess.mutateAsync({
        plan: requestedPlan,
        requestedDays: Number(requestedDays),
        note,
      });
      toast.success('申请已提交，平台管理员审核后会自动生效');
      setDialogOpen(false);
      setNote('');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '申请提交失败');
    }
  };

  if (plansLoading || subscriptionLoading) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 pb-12">
      <header className="flex flex-col gap-4 border-b pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">账户设置</p>
          <h1 className="mt-1 text-2xl font-semibold">会员与用量</h1>
          <p className="mt-2 text-sm text-muted-foreground">会员由平台管理员审核开通，不会自动扣费。</p>
        </div>
        <Button
          onClick={() => setDialogOpen(true)}
          disabled={pendingRequest}
          variant={hasActiveAccess ? 'outline' : 'default'}
        >
          {pendingRequest ? <Clock3 className="mr-2 h-4 w-4" /> : <Send className="mr-2 h-4 w-4" />}
          {pendingRequest ? '申请审核中' : hasActiveAccess ? '申请续期或变更' : '申请开通'}
        </Button>
      </header>

      <section aria-labelledby="membership-status" className="grid gap-6 border-b pb-8 md:grid-cols-[1fr_auto]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="membership-status" className="text-lg font-semibold">
              {PLAN_NAMES[subscription?.plan ?? 'free'] ?? subscription?.plan}
            </h2>
            <MembershipBadge active={hasActiveAccess} status={subscription?.status} />
            {subscription?.access_source?.startsWith('admin') && <Badge variant="outline">平台开通</Badge>}
          </div>
          <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
            {hasActiveAccess
              ? '当前权益已生效。正常使用期间不会显示体验、升级或付费营销提醒。'
              : pendingRequest
                ? '申请已进入平台审核队列，批准后会自动刷新会员状态。'
                : '当前未开通付费会员，可提交所需套餐和使用期限供平台审核。'}
          </p>
          {accessRequest && (
            <p className="mt-3 text-xs text-muted-foreground">
              最近申请：{PLAN_NAMES[accessRequest.requested_plan]} · {accessRequest.requested_days} 天 ·{' '}
              {REQUEST_STATUS[accessRequest.status]}
              {accessRequest.review_reason ? ` · ${accessRequest.review_reason}` : ''}
            </p>
          )}
        </div>
        <div className="min-w-48 border-l pl-6">
          <p className="text-xs text-muted-foreground">会员有效期</p>
          <p className="mt-2 font-medium tabular-nums">
            {subscription?.current_period_end
              ? new Date(subscription.current_period_end).toLocaleDateString('zh-CN')
              : hasActiveAccess
                ? '长期有效'
                : '尚未设置'}
          </p>
          {expiresInDays !== null && expiresInDays > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">剩余 {expiresInDays} 天</p>
          )}
        </div>
      </section>

      {usage && (
        <section aria-labelledby="usage-heading" className="space-y-5 border-b pb-8">
          <div>
            <h2 id="usage-heading" className="font-semibold">本周期用量</h2>
            <p className="mt-1 text-sm text-muted-foreground">配额由当前套餐和管理员调整共同决定。</p>
          </div>
          <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
            <UsageBar label="月度 Token" used={usage.monthly_tokens_used} limit={usage.monthly_token_limit} />
            <UsageBar label="今日 Token" used={usage.daily_tokens_used} limit={usage.daily_token_limit} />
            <UsageBar label="存储空间" used={usage.storage_used_mb} limit={usage.storage_limit_mb} unit="MB" />
          </div>
        </section>
      )}

      <section aria-labelledby="plans-heading" className="space-y-4">
        <div>
          <h2 id="plans-heading" className="font-semibold">可申请套餐</h2>
          <p className="mt-1 text-sm text-muted-foreground">选择套餐后提交申请，最终期限与配额以审核结果为准。</p>
        </div>
        <div className="divide-y border-y">
          {(plans ?? [])
            .filter((plan) => planId(plan) !== 'free')
            .map((plan) => {
              const id = planId(plan);
              const isCurrent = subscription?.plan === id && hasActiveAccess;
              return (
                <div key={id} className="grid gap-4 py-5 md:grid-cols-[180px_1fr_auto] md:items-center">
                  <div>
                    <p className="font-medium">{PLAN_NAMES[id] ?? plan.name}</p>
                    {typeof plan.price_monthly_usd === 'number' && (
                      <p className="mt-1 text-xs text-muted-foreground">参考价 ${plan.price_monthly_usd}/月</p>
                    )}
                  </div>
                  <p className="text-sm leading-6 text-muted-foreground">{plan.features.slice(0, 4).join(' · ')}</p>
                  {isCurrent ? (
                    <Badge variant="secondary">当前套餐</Badge>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setRequestedPlan(id);
                        setDialogOpen(true);
                      }}
                    >
                      申请此套餐
                    </Button>
                  )}
                </div>
              );
            })}
        </div>
      </section>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{hasActiveAccess ? '申请续期或变更' : '申请开通会员'}</DialogTitle>
            <DialogDescription>平台管理员会核对套餐、期限和备注，审核通过后即时生效。</DialogDescription>
          </DialogHeader>
          <div className="space-y-5 py-2">
            <div className="grid gap-2">
              <Label htmlFor="requested-plan">申请套餐</Label>
              <Select value={requestedPlan} onValueChange={setRequestedPlan}>
                <SelectTrigger id="requested-plan"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="starter">团队版</SelectItem>
                  <SelectItem value="professional">专业版</SelectItem>
                  <SelectItem value="enterprise">企业版</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="requested-days">申请期限</Label>
              <Select value={requestedDays} onValueChange={setRequestedDays}>
                <SelectTrigger id="requested-days"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="30">30 天</SelectItem>
                  <SelectItem value="90">90 天</SelectItem>
                  <SelectItem value="180">180 天</SelectItem>
                  <SelectItem value="365">1 年</SelectItem>
                  <SelectItem value="1095">3 年</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="request-note">用途说明</Label>
              <Textarea
                id="request-note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="例如：正式生产使用、续期、增加团队成员等"
                rows={4}
                maxLength={1000}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
            <Button onClick={submitRequest} disabled={requestAccess.isPending}>
              {requestAccess.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              提交审核
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function MembershipBadge({ active, status }: { active: boolean; status?: string }) {
  if (active) {
    return <Badge className="bg-success/10 text-success hover:bg-success/10"><Check className="mr-1 h-3 w-3" />已生效</Badge>;
  }
  if (status === 'expired') {
    return <Badge variant="destructive"><CalendarDays className="mr-1 h-3 w-3" />已到期</Badge>;
  }
  return <Badge variant="secondary"><ShieldCheck className="mr-1 h-3 w-3" />未开通</Badge>;
}

function UsageBar({ label, used, limit, unit = '' }: { label: string; used: number; limit: number; unit?: string }) {
  const percentage = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
  const nearLimit = percentage >= 80;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span>{label}</span>
        <span className={cn('tabular-nums text-muted-foreground', nearLimit && 'text-destructive')}>
          {used.toLocaleString()}{unit} / {limit.toLocaleString()}{unit}
          {nearLimit && <AlertTriangle className="ml-1 inline h-3.5 w-3.5" />}
        </span>
      </div>
      <Progress value={percentage} className={cn('h-1.5', nearLimit && '[&>div]:bg-destructive')} />
    </div>
  );
}

export default BillingDashboard;
