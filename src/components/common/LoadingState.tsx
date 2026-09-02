import { Loader2 } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

interface LoadingStateProps {
  type?: 'skeleton' | 'spinner';
  rows?: number;
  message?: string;
  className?: string;
}

export function LoadingState({
  type = 'skeleton',
  rows = 5,
  message,
  className
}: LoadingStateProps) {
  if (type === 'spinner') {
    return (
      <div aria-busy="true" role="status" className={cn('flex flex-col items-center justify-center py-12', className)}>
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        {message && <p className="mt-4 text-sm text-muted-foreground">{message}</p>}
      </div>
    );
  }

  return (
    <div aria-busy="true" aria-label={message || '正在加载'} className={cn('space-y-2', className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="grid min-h-14 grid-cols-[36px_minmax(0,1fr)_88px] items-center gap-3 border-b py-2.5">
          <Skeleton className="h-8 w-8 rounded-md" />
          <div className="space-y-2">
            <Skeleton className="h-3.5 w-2/5" />
            <Skeleton className="h-3 w-3/4" />
          </div>
          <Skeleton className="h-7 w-full rounded-md" />
        </div>
      ))}
    </div>
  );
}
