import { forwardRef } from 'react';
import { PackageCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export const DeliverableCenterTrigger = forwardRef<HTMLButtonElement, {
  iconOnly?: boolean;
  recentCount: number;
} & React.ComponentPropsWithoutRef<typeof Button>>(
  ({ iconOnly = false, recentCount, className, ...props }, ref) => (
    <Button
      ref={ref}
      variant="ghost"
      size={iconOnly ? 'icon' : 'sm'}
      className={cn('relative text-muted-foreground hover:text-foreground', iconOnly ? 'h-10 w-10' : 'h-8 gap-1.5 px-2.5', className)}
      aria-label="打开成果中心"
      data-testid="deliverable-center-trigger"
      {...props}
    >
      <PackageCheck className="h-4 w-4" />
      {!iconOnly && <span>成果</span>}
      {recentCount > 0 && (
        <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground">
          {recentCount > 9 ? '9+' : recentCount}
        </span>
      )}
    </Button>
  ),
);
DeliverableCenterTrigger.displayName = 'DeliverableCenterTrigger';
