import type { ReactNode } from 'react';
import { AlertCircle, Inbox, Loader2, LockKeyhole, RefreshCw, WifiOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface WorkStateProps {
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
  density?: 'compact' | 'page';
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  tone?: 'empty' | 'error' | 'warning' | 'offline' | 'permission';
}

const STATE_ICON = {
  empty: Inbox,
  error: AlertCircle,
  warning: AlertCircle,
  offline: WifiOff,
  permission: LockKeyhole,
} as const;

const STATE_TONE = {
  empty: 'text-muted-foreground bg-background',
  error: 'border-destructive/25 bg-destructive/5 text-destructive',
  warning: 'border-warning/25 bg-warning/[0.05] text-warning',
  offline: 'border-border bg-muted/40 text-muted-foreground',
  permission: 'border-border bg-muted/40 text-muted-foreground',
} as const;

export function WorkEmptyState({
  title,
  description,
  icon,
  actionLabel,
  onAction,
  className,
  density = 'page',
  secondaryActionLabel,
  onSecondaryAction,
  tone = 'empty',
}: WorkStateProps) {
  const StateIcon = STATE_ICON[tone];
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'border-y border-border/80 bg-card/45 text-center',
        density === 'compact' ? 'px-4 py-5' : 'px-5 py-8',
        className,
      )}
    >
      <div className={cn('mx-auto flex h-9 w-9 items-center justify-center rounded-md border', STATE_TONE[tone])}>
        {icon ?? <StateIcon className="h-5 w-5" />}
      </div>
      <h2 className="mt-3 text-sm font-semibold">{title}</h2>
      {description && <div className="mx-auto mt-1 max-w-md text-sm leading-5 text-muted-foreground">{description}</div>}
      {(actionLabel || secondaryActionLabel) && (
        <div className="mt-3 flex flex-wrap justify-center gap-2">
          {actionLabel && onAction && (
            <Button size="sm" onClick={onAction}>
              {tone === 'error' && <RefreshCw className="h-3.5 w-3.5" />}
              {actionLabel}
            </Button>
          )}
          {secondaryActionLabel && onSecondaryAction && (
            <Button variant="outline" size="sm" onClick={onSecondaryAction}>
              {secondaryActionLabel}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export function WorkErrorState({
  title,
  description,
  actionLabel = '重试',
  onAction,
  className,
}: WorkStateProps) {
  return (
    <WorkEmptyState
      className={className}
      icon={<AlertCircle className="h-6 w-6" />}
      title={title}
      description={description}
      actionLabel={onAction ? actionLabel : undefined}
      onAction={onAction}
      tone="error"
    />
  );
}

export function WorkLoadingState({ title = '正在加载', description, className }: Partial<WorkStateProps>) {
  return (
    <div aria-busy="true" role="status" className={cn('border-y border-border/80 bg-card/45 px-5 py-8 text-center', className)}>
      <Loader2 className="mx-auto h-5 w-5 animate-spin text-primary" />
      <h2 className="mt-3 text-sm font-semibold">{title}</h2>
      {description && <div className="mt-1 text-sm text-muted-foreground">{description}</div>}
    </div>
  );
}
