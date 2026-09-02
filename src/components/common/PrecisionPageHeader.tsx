import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

type HeaderStatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

interface PrecisionPageHeaderProps {
  eyebrow: string;
  title: string;
  description?: ReactNode;
  icon?: LucideIcon;
  actions?: ReactNode;
  metadata?: ReactNode;
  status?: {
    label: string;
    detail?: string;
    tone?: HeaderStatusTone;
  };
  className?: string;
}

const STATUS_VARIANT: Record<HeaderStatusTone, 'subtle' | 'info' | 'success' | 'warning' | 'destructive'> = {
  neutral: 'subtle',
  info: 'info',
  success: 'success',
  warning: 'warning',
  danger: 'destructive',
};

/**
 * Shared heading for high-frequency work surfaces. It keeps hierarchy stable
 * while leaving business pages free to choose their own content layout.
 */
export function PrecisionPageHeader({
  eyebrow,
  title,
  description,
  icon: Icon,
  actions,
  metadata,
  status,
  className,
}: PrecisionPageHeaderProps) {
  const tone = status?.tone ?? 'neutral';

  return (
    <header className={cn('border-b border-border/80 pb-5', className)}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-medium text-primary">
            {Icon && <Icon className="h-4 w-4" aria-hidden="true" />}
            <span>{eyebrow}</span>
          </div>
          <h1 className="mt-2 text-2xl font-semibold leading-8">{title}</h1>
          {description && (
            <div className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
              {description}
            </div>
          )}
        </div>

        {(actions || status) && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {status && (
              <div className="flex items-center gap-2">
                <Badge indicator variant={STATUS_VARIANT[tone]}>{status.label}</Badge>
                {status.detail && <span className="text-xs text-muted-foreground">{status.detail}</span>}
              </div>
            )}
            {actions}
          </div>
        )}
      </div>
      {metadata && <div className="mt-4 border-t border-border/70 pt-3">{metadata}</div>}
    </header>
  );
}

