import { cn } from '@/lib/utils';
import { ButtonHTMLAttributes, forwardRef } from 'react';

interface TouchableProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
}

export const Touchable = forwardRef<HTMLButtonElement, TouchableProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'min-h-[44px] min-w-[44px]',
          'active:scale-95 transition-transform duration-100',
          'focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
          className
        )}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Touchable.displayName = 'Touchable';
