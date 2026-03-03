import React from 'react';
import { CheckCircle2, XCircle, Clock, CircleDot } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ApprovalStep {
  name: string;
  status: 'pending' | 'approved' | 'rejected' | 'current';
  approver?: string;
  time?: string;
}

interface ApprovalFlowProps {
  steps: ApprovalStep[];
  title?: string;
}

const statusConfig = {
  approved: {
    icon: CheckCircle2,
    color: 'text-green-600 dark:text-green-400',
    bg: 'bg-green-50 dark:bg-green-950',
    border: 'border-green-200 dark:border-green-800',
    line: 'bg-green-400 dark:bg-green-600',
    label: '已通过',
  },
  rejected: {
    icon: XCircle,
    color: 'text-red-600 dark:text-red-400',
    bg: 'bg-red-50 dark:bg-red-950',
    border: 'border-red-200 dark:border-red-800',
    line: 'bg-red-400 dark:bg-red-600',
    label: '已拒绝',
  },
  current: {
    icon: CircleDot,
    color: 'text-blue-600 dark:text-blue-400',
    bg: 'bg-blue-50 dark:bg-blue-950',
    border: 'border-blue-200 dark:border-blue-800',
    line: 'bg-blue-400 dark:bg-blue-600',
    label: '审批中',
  },
  pending: {
    icon: Clock,
    color: 'text-amber-600 dark:text-amber-400',
    bg: 'bg-amber-50 dark:bg-amber-950',
    border: 'border-amber-200 dark:border-amber-800',
    line: 'bg-gray-200 dark:bg-gray-700',
    label: '待审批',
  },
};

export default function ApprovalFlow({ steps, title }: ApprovalFlowProps) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="p-4">
      {title && <h4 className="text-sm font-semibold mb-4">{title}</h4>}

      {/* Horizontal layout for large screens */}
      <div className="hidden sm:flex items-start">
        {steps.map((step, i) => {
          const config = statusConfig[step.status];
          const Icon = config.icon;
          const isLast = i === steps.length - 1;

          return (
            <div key={i} className="flex items-start flex-1 min-w-0">
              <div className="flex flex-col items-center min-w-0 flex-1">
                <div className={cn(
                  'w-10 h-10 rounded-full flex items-center justify-center border-2',
                  config.bg,
                  config.border,
                )}>
                  <Icon className={cn('w-5 h-5', config.color)} />
                </div>
                <div className="mt-2 text-center px-1">
                  <p className="text-xs font-medium truncate max-w-[100px]">{step.name}</p>
                  {step.approver && (
                    <p className="text-[10px] text-muted-foreground truncate max-w-[100px]">{step.approver}</p>
                  )}
                  {step.time && (
                    <p className="text-[10px] text-muted-foreground">{step.time}</p>
                  )}
                  <span className={cn('text-[10px] font-medium', config.color)}>
                    {config.label}
                  </span>
                </div>
              </div>
              {!isLast && (
                <div className="flex items-center pt-5 flex-shrink-0">
                  <div className={cn('h-0.5 w-8', config.line)} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Vertical layout for small screens */}
      <div className="sm:hidden flex flex-col gap-0">
        {steps.map((step, i) => {
          const config = statusConfig[step.status];
          const Icon = config.icon;
          const isLast = i === steps.length - 1;

          return (
            <div key={i} className="flex items-stretch gap-3">
              <div className="flex flex-col items-center">
                <div className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center border-2 flex-shrink-0',
                  config.bg,
                  config.border,
                )}>
                  <Icon className={cn('w-4 h-4', config.color)} />
                </div>
                {!isLast && (
                  <div className={cn('w-0.5 flex-1 min-h-[24px]', config.line)} />
                )}
              </div>
              <div className="pb-4 min-w-0">
                <p className="text-sm font-medium">{step.name}</p>
                {step.approver && (
                  <p className="text-xs text-muted-foreground">{step.approver}</p>
                )}
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={cn('text-xs font-medium', config.color)}>
                    {config.label}
                  </span>
                  {step.time && (
                    <span className="text-xs text-muted-foreground">{step.time}</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
