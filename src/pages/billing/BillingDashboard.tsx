/**
 * Billing Dashboard — 订阅管理 + Stripe Checkout + 用量统计
 */
import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import {
  CheckCircle2,
  CreditCard,
  Zap,
  BarChart3,
  AlertTriangle,
  Loader2,
  ExternalLink,
  Crown,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { redirectToCheckout } from '@/lib/stripe';
import {
  usePlans,
  useSubscription,
  useUsageStats,
  useCheckout,
  useCancelSubscription,
  useStartTrial,
  type BillingPlan,
} from '@/hooks/useBilling';

const PLAN_DISPLAY: Record<string, { name: string; color: string }> = {
  free: { name: '免费版', color: 'text-muted-foreground' },
  starter: { name: '基础版', color: 'text-blue-500' },
  professional: { name: '专业版', color: 'text-purple-500' },
  enterprise: { name: '企业版', color: 'text-amber-500' },
};

function BillingDashboard() {
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const { data: plans, isLoading: plansLoading } = usePlans();
  const { data: subscription, isLoading: subLoading } = useSubscription();
  const { data: usage } = useUsageStats();
  const checkout = useCheckout();
  const cancelSub = useCancelSubscription();
  const startTrial = useStartTrial();

  const currentPlan = subscription?.plan || 'free';
  const display = PLAN_DISPLAY[currentPlan] || { name: currentPlan, color: '' };

  const handleCheckout = async (planId: string) => {
    try {
      const baseUrl = window.location.origin;
      const result = await checkout.mutateAsync({
        planId,
        successUrl: `${baseUrl}/billing?success=true`,
        cancelUrl: `${baseUrl}/billing?canceled=true`,
      });
      // If backend returns a Stripe session URL, redirect directly
      if (result.url) {
        window.location.href = result.url;
      } else if (result.session_id) {
        await redirectToCheckout(result.session_id);
      }
    } catch (err) {
      toast.error('支付跳转失败，请重试');
    }
  };

  const handleCancel = async () => {
    if (!confirm('确定取消订阅？取消后将降级为免费版。')) return;
    try {
      await cancelSub.mutateAsync();
      toast.success('订阅已取消');
    } catch {
      toast.error('取消失败');
    }
  };

  const handleTrial = async () => {
    try {
      await startTrial.mutateAsync();
      toast.success('试用已开启');
    } catch {
      toast.error('试用开启失败');
    }
  };

  if (plansLoading || subLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">订阅管理</h1>
          <p className="text-muted-foreground">管理您的订阅计划和用量</p>
        </div>
        {currentPlan === 'free' && (
          <Button variant="outline" onClick={handleTrial}>
            <Zap className="w-4 h-4 mr-1" />
            开启 14 天试用
          </Button>
        )}
      </div>

      {/* 当前订阅状态 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Crown className="w-5 h-5" />
            当前计划
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className={cn('text-xl font-bold', display.color)}>{display.name}</span>
                {subscription?.status === 'trialing' && (
                  <Badge variant="secondary">试用中</Badge>
                )}
                {subscription?.status === 'active' && (
                  <Badge variant="secondary" className="bg-green-500/10 text-green-500">活跃</Badge>
                )}
              </div>
              {subscription?.current_period_end && (
                <p className="text-sm text-muted-foreground">
                  {subscription.status === 'trialing' ? '试用到期' : '下次续费'}：
                  {new Date(subscription.current_period_end).toLocaleDateString('zh-CN')}
                </p>
              )}
            </div>
            {currentPlan !== 'free' && (
              <Button variant="outline" size="sm" onClick={handleCancel} disabled={cancelSub.isPending}>
                取消订阅
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 用量统计 */}
      {usage && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <BarChart3 className="w-5 h-5" />
              用量统计
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <UsageBar label="月度 Token" used={usage.monthly_tokens_used} limit={usage.monthly_token_limit} />
            <UsageBar label="今日 Token" used={usage.daily_tokens_used} limit={usage.daily_token_limit} />
            <UsageBar label="存储空间" used={usage.storage_used_mb} limit={usage.storage_limit_mb} unit="MB" />
          </CardContent>
        </Card>
      )}

      {/* 计划选择 */}
      <div>
        <h2 className="text-lg font-semibold mb-4">选择计划</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {(plans || []).map((plan: BillingPlan) => {
            const isCurrent = plan.id === currentPlan;
            return (
              <Card
                key={plan.id}
                className={cn(
                  'relative transition-all hover:shadow-md',
                  selectedPlan === plan.id && 'ring-2 ring-primary',
                  isCurrent && 'border-primary/50',
                  plan.popular && 'border-primary'
                )}
              >
                {plan.popular && (
                  <Badge className="absolute -top-2 left-1/2 -translate-x-1/2">最受欢迎</Badge>
                )}
                <CardHeader className="text-center">
                  <CardTitle>{plan.name}</CardTitle>
                  <div className="mt-2">
                    <span className="text-3xl font-bold">¥{plan.price}</span>
                    <span className="text-muted-foreground">/月</span>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <ul className="space-y-2">
                    {plan.features.map((f, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm">
                        <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>
                  <Separator />
                  {isCurrent ? (
                    <Button className="w-full" disabled>
                      当前计划
                    </Button>
                  ) : (
                    <Button
                      className="w-full gap-1"
                      variant={plan.popular ? 'default' : 'outline'}
                      onClick={() => handleCheckout(plan.id)}
                      disabled={checkout.isPending}
                    >
                      {checkout.isPending ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <CreditCard className="w-4 h-4" />
                      )}
                      升级到 {plan.name}
                      <ExternalLink className="w-3 h-3" />
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function UsageBar({
  label,
  used,
  limit,
  unit = '',
}: {
  label: string;
  used: number;
  limit: number;
  unit?: string;
}) {
  const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
  const isNearLimit = pct >= 80;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span>{label}</span>
        <span className={cn(isNearLimit && 'text-red-500 font-medium')}>
          {used.toLocaleString()}{unit} / {limit.toLocaleString()}{unit}
          {isNearLimit && <AlertTriangle className="w-3 h-3 inline ml-1" />}
        </span>
      </div>
      <Progress value={pct} className={cn(isNearLimit && '[&>div]:bg-red-500')} />
    </div>
  );
}

export default BillingDashboard;
