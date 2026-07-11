import React from 'react';
import { CheckCircle2, Loader2 } from 'lucide-react';
import type { TraceStep } from '@/hooks/useAgentTrace';

interface WorkflowStepperProps {
  steps: TraceStep[];
  isActive: boolean;
  onOpenTrace: () => void;
}

function stepLabel(step?: TraceStep) {
  if (!step) return '准备处理';
  if (step.name) return step.name;
  if (step.type === 'tool_call') return '调用业务工具';
  if (step.type === 'thinking') return '理解任务';
  return '处理中';
}

/**
 * Business users see status and outcome. Full traces remain available on
 * demand without turning the conversation into an engineering console.
 */
export const WorkflowStepper: React.FC<WorkflowStepperProps> = ({
  steps,
  isActive,
  onOpenTrace,
}) => {
  const displaySteps = steps.filter((step) => step.type !== 'tool_result');
  const runningStep = [...displaySteps].reverse().find((step) => step.status === 'running');
  const completedCount = displaySteps.filter((step) => step.status === 'success').length;

  if (!isActive && displaySteps.length === 0) return null;

  return (
    <div className="mx-4 mb-2 flex min-h-10 items-center justify-between gap-3 border-l-2 border-primary/45 bg-muted/30 px-3 py-2">
      <div className="flex min-w-0 items-center gap-2">
        {isActive ? (
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
        ) : (
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-success" />
        )}
        <span className="truncate text-xs text-foreground">
          {isActive ? stepLabel(runningStep) : `已完成 ${completedCount} 个执行步骤`}
        </span>
      </div>
      <button
        type="button"
        onClick={onOpenTrace}
        className="shrink-0 text-xs text-muted-foreground transition-colors hover:text-foreground"
      >
        执行记录
      </button>
    </div>
  );
};
