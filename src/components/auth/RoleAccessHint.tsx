import { useEffect } from 'react';
import { ShieldAlert } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface RoleAccessHintProps {
  title?: string;
  description?: string;
  requiredRoles?: string[];
  redirectTo?: string;
  autoRedirectMs?: number;
  className?: string;
}

export function RoleAccessHint({
  title = '当前角色没有访问权限',
  description = '为了保护业务数据和审批权限，系统会把你带回可访问的工作台。',
  requiredRoles = [],
  redirectTo = '/dashboard',
  autoRedirectMs = 1200,
  className,
}: RoleAccessHintProps) {
  const navigate = useNavigate();

  useEffect(() => {
    if (!autoRedirectMs) return undefined;
    const timer = window.setTimeout(() => navigate(redirectTo, { replace: true }), autoRedirectMs);
    return () => window.clearTimeout(timer);
  }, [autoRedirectMs, navigate, redirectTo]);

  return (
    <div
      data-testid="role-access-hint"
      className={cn('mx-auto flex min-h-[420px] max-w-lg flex-col items-center justify-center p-6 text-center', className)}
    >
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-lg bg-amber-500/10 text-amber-600">
        <ShieldAlert className="h-7 w-7" />
      </div>
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
      {requiredRoles.length > 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          需要角色：{requiredRoles.join(' / ')}
        </p>
      )}
      <Button className="mt-6" onClick={() => navigate(redirectTo, { replace: true })}>
        返回我的工作台
      </Button>
    </div>
  );
}

export default RoleAccessHint;
