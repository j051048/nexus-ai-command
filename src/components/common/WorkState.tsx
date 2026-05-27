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
}

export function WorkEmptyState({
  title,
  description,
  icon = <Inbox className="h-6 w-6" />,
  actionLabel,
  onAction,
  className,
}: WorkStateProps) {
  return (
    <div className={cn('rounded-lg border bg-card p-8 text-center shadow-sm', className)}>
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        {icon}
      </div>
      <h2 className="mt-4 font-semibold">{title}</h2>
      {description && <div className="mx-auto mt-1 max-w-md text-sm leading-6 text-muted-foreground">{description}</div>}
      {actionLabel && onAction && (
        <Button className="mt-4" size="sm" onClick={onAction}>
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
    <div className={cn('rounded-lg border bg-card p-8 text-center shadow-sm', className)}>
      <Loader2 className="mx-auto h-6 w-6 animate-spin text-primary" />
      <h2 className="mt-4 font-semibold">{title}</h2>
      {description && <div className="mt-1 text-sm text-muted-foreground">{description}</div>}
    </div>
  );
}
