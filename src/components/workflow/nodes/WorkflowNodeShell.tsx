import { Handle, Position } from '@xyflow/react';
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

export type WorkflowNodeTone = 'primary' | 'success' | 'warning' | 'info' | 'neutral';

const TONE = {
  primary: {
    bar: 'bg-primary',
    icon: 'border-primary/20 bg-primary/[0.08] text-primary',
    handle: '!bg-primary',
  },
  success: {
    bar: 'bg-success',
    icon: 'border-success/20 bg-success/[0.08] text-success',
    handle: '!bg-success',
  },
  warning: {
    bar: 'bg-warning',
    icon: 'border-warning/20 bg-warning/[0.08] text-warning',
    handle: '!bg-warning',
  },
  info: {
    bar: 'bg-[hsl(var(--data-accent))]',
    icon: 'border-primary/15 bg-primary/[0.06] text-primary',
    handle: '!bg-[hsl(var(--data-accent))]',
  },
  neutral: {
    bar: 'bg-muted-foreground',
    icon: 'border-border bg-muted/60 text-muted-foreground',
    handle: '!bg-muted-foreground',
  },
} as const;

interface WorkflowNodeShellProps {
  selected?: boolean;
  icon: LucideIcon;
  typeLabel: string;
  title: string;
  tone?: WorkflowNodeTone;
  target?: boolean;
  source?: boolean;
  sourceId?: string;
  children?: ReactNode;
  className?: string;
}

export function workflowHandleClass(tone: WorkflowNodeTone = 'neutral') {
  return cn('!h-2.5 !w-2.5 !border-2 !border-background', TONE[tone].handle);
}

/** Stable, low-noise shell shared by every workflow node type. */
export function WorkflowNodeShell({
  selected = false,
  icon: Icon,
  typeLabel,
  title,
  tone = 'neutral',
  target = true,
  source = true,
  sourceId,
  children,
  className,
}: WorkflowNodeShellProps) {
  const colors = TONE[tone];
  return (
    <div
      className={cn(
        'relative min-w-[184px] rounded-md border bg-card px-3.5 py-3 shadow-[var(--shadow-card)] transition-[border-color,box-shadow] duration-150',
        selected ? 'border-primary ring-2 ring-primary/[0.15] shadow-[var(--shadow-elevated)]' : 'border-border hover:border-foreground/20',
        className,
      )}
    >
      <span aria-hidden="true" className={cn('absolute inset-y-0 left-0 w-0.5', colors.bar)} />
      {target && <Handle type="target" position={Position.Top} className={workflowHandleClass(tone)} />}
      <div className="flex items-center gap-2.5">
        <span className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-md border', colors.icon)}>
          <Icon className="h-3.5 w-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-medium text-muted-foreground">{typeLabel}</div>
          <div className="mt-0.5 truncate text-sm font-semibold" title={title}>{title}</div>
        </div>
      </div>
      {children && <div className="mt-3 border-t border-border/70 pt-2.5">{children}</div>}
      {source && <Handle type="source" id={sourceId} position={Position.Bottom} className={workflowHandleClass(tone)} />}
    </div>
  );
}
