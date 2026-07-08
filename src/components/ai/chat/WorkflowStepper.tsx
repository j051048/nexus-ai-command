import React from 'react';
import { CheckCircle2, Loader2, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TraceStep } from '@/hooks/useAgentTrace';

interface WorkflowStepperProps {
  steps: TraceStep[];
  isActive: boolean;
  onOpenTrace: () => void;
}

function stepLabel(step?: TraceStep) {
  if (!step) return '准备处理';
  if (step.name) return step.name;
  if (step.type === 'tool_call') return '调用工具';
  if (step.type === 'thinking') return '理解任务';
  return '处理中';
}

export const WorkflowStepper: React.FC<WorkflowStepperProps> = ({
  steps,
  isActive,
  onOpenTrace,
}) => {
  const displaySteps = steps.filter((step) => step.type !== 'tool_result');
  const runningStep = [...displaySteps].reverse().find((step) => step.status === 'running');
  const completedCount = displaySteps.filter((step) => step.status === 'success').length;
  const totalCount = Math.max(displaySteps.length, isActive ? completedCount + 1 : completedCount);

  if (!isActive && displaySteps.length === 0) return null;

  return (
    <div className="mx-4 mb-3 rounded-xl border bg-card/90 px-3 py-2.5 shadow-sm animate-in fade-in slide-in-from-bottom-1 duration-300">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <div
            className={cn(
              'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
              isActive ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground',
            )}
          >
            {isActive ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              <span>{isActive ? 'AI 正在处理' : 'AI 已完成'}</span>
            </div>
            <p className="truncate text-xs text-muted-foreground">
              {isActive ? stepLabel(runningStep) : `已完成 ${completedCount} 个执行步骤`}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          {totalCount > 0 && (
            <div className="hidden items-center gap-1.5 sm:flex" aria-label={`已完成 ${completedCount} / ${totalCount}`}>
              {Array.from({ length: Math.min(totalCount, 5) }).map((_, index) => (
                <span
                  key={index}
                  className={cn(
                    'h-1.5 w-1.5 rounded-full',
                    index < completedCount ? 'bg-primary' : 'bg-muted-foreground/25',
                  )}
                />
              ))}
            </div>
          )}
          <button
            onClick={onOpenTrace}
            className="text-xs font-medium text-muted-foreground transition-colors hover:text-primary"
          >
            执行记录
          </button>
        </div>
      </div>
    </div>
  );
};
