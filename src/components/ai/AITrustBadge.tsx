import { ShieldCheck, ShieldAlert } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export type AITrustLevel = 'high' | 'medium' | 'low';

const TRUST_META: Record<AITrustLevel, { label: string; className: string }> = {
  high: {
    label: '高置信',
    className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  },
  medium: {
    label: '需复核',
    className: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300',
  },
  low: {
    label: '低置信',
    className: 'border-destructive/30 bg-destructive/10 text-destructive',
  },
};

export function AITrustBadge({
  level = 'medium',
  score,
  className,
}: {
  level?: AITrustLevel;
  score?: number;
  className?: string;
}) {
  const meta = TRUST_META[level];
  const Icon = level === 'low' ? ShieldAlert : ShieldCheck;
  return (
    <Badge variant="outline" className={cn('gap-1 rounded-md font-medium', meta.className, className)}>
      <Icon className="h-3.5 w-3.5" />
      {meta.label}
      {typeof score === 'number' ? ` ${Math.round(score)}%` : ''}
    </Badge>
  );
}

export default AITrustBadge;
