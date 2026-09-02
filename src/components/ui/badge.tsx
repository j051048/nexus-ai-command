/* eslint-disable react-refresh/only-export-components */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border border-primary/20 bg-primary/10 text-primary",
        secondary: "border border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "border border-destructive/20 bg-destructive/10 text-destructive hover:bg-destructive/20",
        outline: "border border-border text-foreground bg-background/50",
        success: "border border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
        warning: "border border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-400",
        info: "border border-sky-500/20 bg-sky-500/10 text-sky-600 dark:text-sky-400",
        subtle: "border border-border/50 bg-muted/50 text-muted-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {
  indicator?: boolean;
}

function Badge({ className, variant, indicator = false, children, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), indicator && 'gap-1.5', className)} {...props}>
      {indicator && <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current opacity-75" />}
      {children}
    </div>
  );
}

export { Badge, badgeVariants };
