import type { ReactNode } from 'react';
import { AlertCircle, Inbox, Loader2 } from 'lucide-react';
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
}

export function WorkEmptyState({
  title,
  description,
  icon = <Inbox className="h-6 w-6" />,
  actionLabel,
  onAction,
  className,
  density = 'page',
}: WorkStateProps) {
  return (
    <div
      className={cn(
        'border-y bg-card/45 text-center',
        density === 'compact' ? 'px-4 py-5' : 'px-5 py-8',
        className,
      )}
    >
      <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-md border bg-background text-muted-foreground">
        {icon}
      </div>
      <h2 className="mt-3 text-sm font-semibold">{title}</h2>
      {description && <div className="mx-auto mt-1 max-w-md text-sm leading-5 text-muted-foreground">{description}</div>}
      {actionLabel && onAction && (
        <Button className="mt-3" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
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
    />
  );
}

export function WorkLoadingState({ title = '正在加载', description, className }: Partial<WorkStateProps>) {
  return (
    <div className={cn('border-y bg-card/45 px-5 py-8 text-center', className)}>
      <Loader2 className="mx-auto h-5 w-5 animate-spin text-primary" />
      <h2 className="mt-3 text-sm font-semibold">{title}</h2>
      {description && <div className="mt-1 text-sm text-muted-foreground">{description}</div>}
    </div>
  );
}
