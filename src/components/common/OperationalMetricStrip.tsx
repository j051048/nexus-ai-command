import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface OperationalMetric {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  tone?: 'default' | 'danger' | 'warning' | 'success';
}

interface OperationalMetricStripProps {
  metrics: OperationalMetric[];
  ariaLabel?: string;
  className?: string;
}

const VALUE_TONES: Record<NonNullable<OperationalMetric['tone']>, string> = {
  default: 'text-foreground',
  danger: 'text-destructive',
  warning: 'text-amber-700 dark:text-amber-300',
  success: 'text-emerald-700 dark:text-emerald-300',
};

/**
 * Dense, card-free instrumentation for operational pages. Values use stable,
 * tabular numerals so live updates never shift the surrounding layout.
 */
export function OperationalMetricStrip({
  metrics,
  ariaLabel = '运营指标',
  className,
}: OperationalMetricStripProps) {
  return (
    <dl
      aria-label={ariaLabel}
      className={cn(
        'grid overflow-hidden border-y bg-card/45',
        metrics.length <= 3 ? 'grid-cols-3' : 'grid-cols-2 md:grid-cols-5',
        className,
      )}
    >
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="min-w-0 border-b px-3 py-2.5 last:border-b-0 odd:border-r md:border-b-0 md:border-r md:last:border-r-0"
        >
          <dt className="truncate text-[11px] font-medium text-muted-foreground">{metric.label}</dt>
          <dd
            className={cn(
              'mt-0.5 truncate text-lg font-semibold tabular-nums',
              VALUE_TONES[metric.tone ?? 'default'],
            )}
          >
            {metric.value}
          </dd>
          {metric.detail && (
            <div className="mt-0.5 truncate text-[11px] text-muted-foreground">{metric.detail}</div>
          )}
        </div>
      ))}
    </dl>
  );
}

