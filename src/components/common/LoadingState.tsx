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
      <div className={cn('flex flex-col items-center justify-center py-12', className)}>
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        {message && <p className="mt-4 text-sm text-muted-foreground">{message}</p>}
      </div>
    );
  }

  return (
    <div className={cn('space-y-3', className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full" />
      ))}
    </div>
  );
}
