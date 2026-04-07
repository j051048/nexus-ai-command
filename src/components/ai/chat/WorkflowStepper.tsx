import React from 'react';
import { CheckCircle2, Circle, Loader2, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TraceStep } from '@/hooks/useAgentTrace';

interface WorkflowStepperProps {
  steps: TraceStep[];
  isActive: boolean;
  onOpenTrace: () => void;
}

export const WorkflowStepper: React.FC<WorkflowStepperProps> = ({ steps, isActive, onOpenTrace }) => {
  // Filter only significant steps (thinking and tool calls)
  const displaySteps = steps.filter(s => s.type !== 'tool_result').slice(-4);
  
  if (displaySteps.length === 0 && !isActive) return null;

  return (
    <div className="mx-4 mb-4 p-4 rounded-2xl border border-primary/20 bg-primary/5 backdrop-blur-sm animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-primary animate-pulse" />
          <span className="text-sm font-bold text-foreground/80">正在执行流水线任务</span>
        </div>
        <button 
          onClick={onOpenTrace}
          className="text-[10px] font-bold uppercase tracking-wider text-primary hover:underline"
        >
          查看详情日志
        </button>
      </div>

      <div className="flex items-center gap-2">
        {displaySteps.map((step, idx) => (
          <React.Fragment key={idx}>
            {idx > 0 && (
              <div className={cn(
                "h-[2px] flex-1 rounded-full",
                step.status === 'success' ? "bg-primary" : "bg-muted"
              )} />
            )}
            <div className="flex flex-col items-center gap-2 group relative">
              <div className={cn(
                "w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-300 border",
                step.status === 'success' ? "bg-primary border-primary text-white" : 
                step.status === 'running' ? "bg-primary/20 border-primary/40 text-primary animate-pulse shadow-[0_0_15px_rgba(var(--primary-rgb),0.3)]" :
                "bg-muted border-border text-muted-foreground"
              )}>
                {step.status === 'success' ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : step.status === 'running' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Circle className="w-3 h-3 fill-current opacity-30" />
                )}
              </div>
              <span className={cn(
                "text-[10px] font-bold whitespace-nowrap absolute -bottom-6 opacity-0 group-hover:opacity-100 transition-opacity",
                step.status === 'running' && "opacity-100 text-primary"
              )}>
                {step.name || (step.type === 'thinking' ? '思考中' : '处理中')}
              </span>
            </div>
          </React.Fragment>
        ))}
        {isActive && (
          <>
            <div className="h-[2px] flex-1 rounded-full bg-muted animate-pulse" />
            <div className="w-8 h-8 rounded-xl bg-muted border border-border flex items-center justify-center animate-pulse">
               <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/30" />
            </div>
          </>
        )}
      </div>
      
      {/* Spacer for the absolute labels */}
      <div className="h-4" />
    </div>
  );
};
