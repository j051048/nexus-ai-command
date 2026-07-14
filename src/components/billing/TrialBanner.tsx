import { useMemo, useState } from 'react';
import { AlertTriangle, ArrowRight, ShieldCheck, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { useSubscription } from '@/hooks/useBilling';

const DISMISSED_NOTICE_KEY = 'nexus:billing-notice-dismissed';

/**
 * Global billing notices are reserved for access problems.
 * Free, pending, trialing, and valid admin-approved memberships stay quiet.
 */
export function TrialBanner() {
  const { data: subscription, isLoading, isError } = useSubscription();
  const navigate = useNavigate();
  const noticeId = useMemo(
    () =>
      subscription
        ? [subscription.org_id, subscription.status, subscription.current_period_end ?? 'open'].join(':')
        : '',
    [subscription],
  );
  const [dismissedNotice, setDismissedNotice] = useState(() => localStorage.getItem(DISMISSED_NOTICE_KEY) ?? '');

  if (
    isLoading ||
    isError ||
    !subscription ||
    subscription.notice_policy !== 'action_required' ||
    dismissedNotice === noticeId
  ) {
    return null;
  }

  const isPastDue = subscription.status === 'past_due';
  const title = isPastDue ? '会员状态需要确认' : '会员有效期已结束';
  const description = isPastDue ? '请联系平台管理员核对开通记录。' : '可在订阅管理中提交续期申请。';

  return (
    <div className="flex min-h-10 items-center justify-between gap-4 border-b bg-destructive/5 px-4 py-2 text-sm">
      <div className="flex min-w-0 items-center gap-2">
        <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" />
        <p className="truncate">
          <span className="font-medium text-foreground">{title}</span>
          <span className="ml-2 text-muted-foreground">{description}</span>
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <Button variant="ghost" size="sm" className="h-7 gap-1 px-2" onClick={() => navigate('/billing')}>
          查看状态
          <ArrowRight className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          aria-label="关闭会员状态提醒"
          onClick={() => {
            localStorage.setItem(DISMISSED_NOTICE_KEY, noticeId);
            setDismissedNotice(noticeId);
          }}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePaywall(requiredPlan: 'starter' | 'professional' | 'enterprise' = 'starter') {
  const { data: subscription } = useSubscription();
  const navigate = useNavigate();
  const planRank: Record<string, number> = { free: 0, starter: 1, professional: 2, enterprise: 3 };
  const currentRank = planRank[subscription?.plan ?? 'free'] ?? 0;
  const canAccess = Boolean(subscription?.has_paid_access && currentRank >= planRank[requiredPlan]);

  const showUpgrade = () => (
    <div className="mx-auto flex max-w-lg flex-col items-center justify-center gap-4 border-y py-12 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted">
        <ShieldCheck className="h-5 w-5 text-muted-foreground" />
      </div>
      <div>
        <h3 className="font-semibold">该能力尚未开通</h3>
        <p className="mt-1 text-sm text-muted-foreground">提交申请后，由平台管理员审核套餐与有效期。</p>
      </div>
      <Button onClick={() => navigate('/billing')}>申请开通</Button>
    </div>
  );

  return { canAccess, showUpgrade };
}
