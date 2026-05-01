/**
 * TrialBanner - 试用引导横幅
 *
 * Free 用户: 显示"免费体验14天全功能"横幅
 * 试用中用户: 显示剩余天数倒计时
 * 付费用户: 不显示
 */
import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Zap, X, Crown, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSubscription, useStartTrial } from '@/hooks/useBilling';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

const BANNER_DISMISSED_KEY = 'nexus:trial-banner-dismissed';

export function TrialBanner() {
  const { data: subscription, isLoading } = useSubscription();
  const startTrial = useStartTrial();
  const navigate = useNavigate();

  const [dismissed, setDismissed] = useState(() => {
    const stored = localStorage.getItem(BANNER_DISMISSED_KEY);
    if (!stored) return false;
    // 每天最多dismiss一次，第二天重新显示
    const dismissedAt = new Date(stored);
    const now = new Date();
    return dismissedAt.toDateString() === now.toDateString();
  });

  if (isLoading || dismissed) return null;

  const plan = subscription?.plan || 'free';
  const status = subscription?.status || 'active';

  // 付费活跃用户不显示
  if (plan !== 'free' && status === 'active') return null;

  // 试用中 - 显示倒计时
  if (status === 'trialing' && subscription?.current_period_end) {
    const endDate = new Date(subscription.current_period_end);
    const now = new Date();
    const daysLeft = Math.max(0, Math.ceil((endDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)));

    if (daysLeft <= 0) return null;

    return (
      <div className="relative flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-purple-500/10 via-blue-500/10 to-cyan-500/10 border-b border-purple-500/20">
        <div className="flex items-center gap-2 text-sm">
          <Crown className="w-4 h-4 text-purple-500" />
          <span className="text-foreground/80">
            专业版试用中 · 还剩 <strong className="text-purple-500">{daysLeft} 天</strong>
          </span>
          <Clock className="w-3.5 h-3.5 text-muted-foreground" />
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs border-purple-500/30 hover:bg-purple-500/10"
            onClick={() => navigate('/billing')}
          >
            升级为正式版
          </Button>
          <button
            onClick={() => {
              localStorage.setItem(BANNER_DISMISSED_KEY, new Date().toISOString());
              setDismissed(true);
            }}
            className="text-muted-foreground hover:text-foreground p-0.5"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    );
  }

  // Free 用户 - 显示试用引导
  if (plan === 'free') {
    const handleStartTrial = async () => {
      try {
        await startTrial.mutateAsync(14);
        toast.success('14天全功能试用已开启!');
      } catch {
        toast.error('试用开启失败，请稍后重试');
      }
    };

    return (
      <div className="relative flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-amber-500/10 via-orange-500/10 to-rose-500/10 border-b border-amber-500/20">
        <div className="flex items-center gap-2 text-sm">
          <Zap className="w-4 h-4 text-amber-500" />
          <span className="text-foreground/80">
            解锁全部 AI 能力 · <strong className="text-amber-600 dark:text-amber-400">免费体验 14 天</strong>专业版功能
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            className="h-7 text-xs bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white border-0"
            onClick={handleStartTrial}
            disabled={startTrial.isPending}
          >
            {startTrial.isPending ? '开启中...' : '立即体验'}
          </Button>
          <button
            onClick={() => {
              localStorage.setItem(BANNER_DISMISSED_KEY, new Date().toISOString());
              setDismissed(true);
            }}
            className="text-muted-foreground hover:text-foreground p-0.5"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    );
  }

  return null;
}

/**
 * usePaywall - 付费墙检测 hook
 *
 * 用法:
 * const { canAccess, showUpgrade } = usePaywall('professional');
 * if (!canAccess) return showUpgrade();
 */
// eslint-disable-next-line react-refresh/only-export-components
export function usePaywall(requiredPlan: 'starter' | 'professional' | 'enterprise' = 'starter') {
  const { data: subscription } = useSubscription();
  const startTrial = useStartTrial();
  const navigate = useNavigate();

  const planRank: Record<string, number> = {
    free: 0,
    starter: 1,
    professional: 2,
    enterprise: 3,
  };

  const currentPlan = subscription?.plan || 'free';
  const isTrialing = subscription?.status === 'trialing';
  const canAccess = isTrialing || planRank[currentPlan] >= planRank[requiredPlan];

  const showUpgrade = () => {
    const planNames: Record<string, string> = {
      starter: '基础版',
      professional: '专业版',
      enterprise: '企业版',
    };

    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4 text-center">
        <Crown className="w-12 h-12 text-amber-500" />
        <h3 className="text-lg font-semibold">此功能需要 {planNames[requiredPlan]} 及以上</h3>
        <p className="text-sm text-muted-foreground max-w-md">
          升级您的订阅计划或开启 14 天免费试用来体验全部功能
        </p>
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={async () => {
              try {
                await startTrial.mutateAsync(14);
                toast.success('试用已开启!');
              } catch {
                toast.error('试用开启失败');
              }
            }}
          >
            <Zap className="w-4 h-4 mr-1" />
            免费试用 14 天
          </Button>
          <Button onClick={() => navigate('/billing')}>
            查看定价
          </Button>
        </div>
      </div>
    );
  };

  return { canAccess, showUpgrade };
}
