import { useMemo } from 'react';
import type { QuotaInfo } from '@/hooks/useAIStream';
import { Progress } from '@/components/ui/progress';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { Activity } from 'lucide-react';

interface QuotaDisplayProps {
  quotaInfo: QuotaInfo | null;
}

export function QuotaDisplay({ quotaInfo }: QuotaDisplayProps) {
  if (!quotaInfo) return null;

  const { tokens_used, tokens_limit, tokens_remaining, cost_usd, requests, requests_limit } = quotaInfo;

  const usagePercent = useMemo(() => {
    if (!tokens_limit) return 0;
    return Math.round(((tokens_limit - tokens_remaining) / tokens_limit) * 100);
  }, [tokens_limit, tokens_remaining]);

  const remainPercent = useMemo(() => {
    if (!tokens_limit) return 100;
    return Math.round((tokens_remaining / tokens_limit) * 100);
  }, [tokens_limit, tokens_remaining]);

  const statusColor = remainPercent > 20
    ? 'text-muted-foreground'
    : remainPercent > 5
      ? 'text-orange-500'
      : 'text-destructive';

  const progressColor = remainPercent > 20
    ? '[&>div]:bg-primary'
    : remainPercent > 5
      ? '[&>div]:bg-orange-500'
      : '[&>div]:bg-destructive';

  const formatTokens = (n: number) => {
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return String(n);
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={cn(
            'flex items-center gap-2 px-3 py-1.5 text-xs rounded-md',
            'bg-muted/50 border border-border/50',
            'transition-colors duration-200',
            statusColor
          )}>
            <Activity className="h-3 w-3 shrink-0" />
            <span className="whitespace-nowrap">
              {formatTokens(tokens_used)} tokens
            </span>
            {cost_usd > 0 && (
              <span className="whitespace-nowrap">
                · ${cost_usd.toFixed(4)}
              </span>
            )}
            <Progress
              value={usagePercent}
              className={cn('h-1.5 w-16 shrink-0', progressColor)}
            />
          </div>
        </TooltipTrigger>
        <TooltipContent side="top" className="text-xs">
          <div className="space-y-1">
            <div>Token 已用: {tokens_used.toLocaleString()} / {tokens_limit.toLocaleString()}</div>
            <div>Token 剩余: {tokens_remaining.toLocaleString()} ({remainPercent}%)</div>
            <div>请求次数: {requests} / {requests_limit}</div>
            {cost_usd > 0 && <div>本次费用: ${cost_usd.toFixed(4)}</div>}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
