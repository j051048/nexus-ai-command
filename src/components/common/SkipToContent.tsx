import { cn } from '@/lib/utils';

export function SkipToContent() {
  return (
    <a
      href="#main-content"
      className={cn(
        'sr-only focus:not-sr-only',
        'fixed top-4 left-4 z-50',
        'bg-primary text-primary-foreground',
        'px-4 py-2 rounded-md',
        'focus:ring-2 focus:ring-primary focus:ring-offset-2'
      )}
    >
      跳到主内容
    </a>
  );
}
