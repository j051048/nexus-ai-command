import type { ReactNode } from 'react';
import { LockKeyhole, Send } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { useSubscription } from '@/hooks/useBilling';

export function MembershipGate({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { data: subscription, isLoading, isError } = useSubscription();

  if (isLoading) {
    return (
      <div
        className="min-h-48 animate-pulse border-y bg-muted/20"
        aria-label="正在检查企业会员状态"
      />
    );
  }

  // A temporary billing-service outage must not lock an otherwise valid tenant
  // out of its workspace. Backend authorization remains the final authority.
  if (isError || subscription?.has_paid_access) {
    return <>{children}</>;
  }

  return (
    <section className="mx-auto flex min-h-[55vh] max-w-xl flex-col items-center justify-center px-6 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-md border bg-muted/30">
        <LockKeyhole className="h-5 w-5 text-muted-foreground" />
      </div>
      <h2 className="mt-5 text-lg font-semibold">该功能需要企业会员</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
        会员按企业统一开通。审核通过后，企业内所有成员都会自动获得完整功能，无需逐个配置。
      </p>
      <Button className="mt-5" onClick={() => navigate('/billing')}>
        <Send className="mr-2 h-4 w-4" />
        申请开通
      </Button>
    </section>
  );
}
