import { useMemo, useState } from 'react';
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  FileCode2,
  Loader2,
  X,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { AgentTrace, TraceStep } from '@/hooks/useAgentTrace';
import type { OrchestrationTrace } from '@/hooks/useOrchestrationTrace';
import { OrchestrationPanel } from './OrchestrationPanel';

interface AgentTracePanelProps {
  trace: AgentTrace;
  className?: string;
  defaultExpanded?: boolean;
  onClose?: () => void;
  orchestration?: OrchestrationTrace;
}

function getBusinessLabel(step: TraceStep) {
  if (step.type === 'thinking') return '理解任务';
  if (step.type === 'tool_call') return step.name ? `调用 ${step.name}` : '调用业务工具';
  if (step.type === 'tool_progress') return step.name ? `执行 ${step.name}` : '执行业务动作';
  if (step.type === 'tool_result') return '核对执行结果';
  return step.name || '处理任务';
}

function StepStatusIcon({ status }: { status?: TraceStep['status'] }) {
  if (status === 'running') return <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />;
  if (status === 'error') return <XCircle className="h-3.5 w-3.5 text-destructive" />;
  return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700 dark:text-emerald-300" />;
}

function BusinessStepRow({ step }: { step: TraceStep }) {
  return (
    <div className="grid min-h-9 grid-cols-[20px_minmax(0,1fr)_auto] items-center gap-2 border-b px-3 py-2 last:border-b-0">
      <StepStatusIcon status={step.status} />
      <span className="truncate text-xs text-foreground">{getBusinessLabel(step)}</span>
      {step.duration_ms && step.duration_ms > 0 ? (
        <span className="text-[11px] tabular-nums text-muted-foreground">{step.duration_ms} ms</span>
      ) : null}
    </div>
  );
}

function TechnicalStep({ step, index }: { step: TraceStep; index: number }) {
  return (
    <details className="border-b px-3 py-2 last:border-b-0">
      <summary className="cursor-pointer list-none text-xs font-medium text-foreground">
        <span className="mr-2 text-muted-foreground">{String(index + 1).padStart(2, '0')}</span>
        {step.type} {step.name ? `· ${step.name}` : ''}
      </summary>
      <div className="mt-2 space-y-2 pl-6 text-[11px] leading-5 text-muted-foreground">
        {step.content && <p className="whitespace-pre-wrap break-words">{step.content}</p>}
        {step.args && (
          <pre className="max-h-40 overflow-auto rounded-md border bg-muted/35 p-2 font-mono text-foreground/80">
            {step.args}
          </pre>
        )}
      </div>
    </details>
  );
}

/**
 * Business users get progress, duration and outcome first. Raw model/tool
 * details stay available behind an explicit technical-details control.
 */
export function AgentTracePanel({
  trace,
  className,
  defaultExpanded = false,
  onClose,
  orchestration,
}: AgentTracePanelProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [showTechnical, setShowTechnical] = useState(false);

  const stats = useMemo(() => {
    const visibleSteps = trace.steps.filter((step) => step.type !== 'tool_result');
    const toolCount = trace.steps.filter((step) => step.type === 'tool_call').length;
    const failedCount = trace.steps.filter((step) => step.status === 'error').length;
    const duration = trace.startTime && trace.endTime ? trace.endTime - trace.startTime : null;
    return { visibleSteps, toolCount, failedCount, duration };
  }, [trace]);

  if (trace.steps.length === 0 && !trace.isActive) return null;

  return (
    <section className={cn('overflow-hidden border-y bg-card/60', className)}>
      <div className="flex min-h-11 items-center justify-between gap-3 px-3 py-2">
        <button
          type="button"
          onClick={() => setIsExpanded((value) => !value)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          aria-expanded={isExpanded}
        >
          {trace.isActive ? (
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
          ) : (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-300" />
          )}
          <span className="truncate text-xs font-medium">
            {trace.isActive ? 'AI 正在执行业务任务' : '任务执行完成'}
          </span>
          <span className="hidden text-[11px] text-muted-foreground sm:inline">
            {stats.visibleSteps.length} 步 · {stats.toolCount} 次工具调用
          </span>
        </button>

        <div className="flex items-center gap-1">
          {stats.failedCount > 0 && <Badge variant="destructive">{stats.failedCount} 个异常</Badge>}
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs text-muted-foreground"
            onClick={() => setIsExpanded((value) => !value)}
          >
            {isExpanded ? '收起' : '执行详情'}
            {isExpanded ? <ChevronUp className="ml-1 h-3.5 w-3.5" /> : <ChevronDown className="ml-1 h-3.5 w-3.5" />}
          </Button>
          {onClose && (
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose} aria-label="关闭执行详情">
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="border-t">
          <div className="flex flex-wrap items-center justify-between gap-2 bg-muted/20 px-3 py-2 text-[11px] text-muted-foreground">
            <div className="flex items-center gap-3">
              {stats.duration && (
                <span className="inline-flex items-center gap-1 tabular-nums">
                  <Clock className="h-3 w-3" />
                  {(stats.duration / 1000).toFixed(1)} 秒
                </span>
              )}
              {trace.totalTokens > 0 && <span className="tabular-nums">{trace.totalTokens} tokens</span>}
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-[11px]"
              onClick={() => setShowTechnical((value) => !value)}
            >
              <FileCode2 className="mr-1 h-3.5 w-3.5" />
              {showTechnical ? '隐藏技术详情' : '技术详情'}
            </Button>
          </div>

          {!showTechnical ? (
            <div className="max-h-64 overflow-y-auto">
              {stats.visibleSteps.map((step, index) => (
                <BusinessStepRow key={`${index}-${step.timestamp}`} step={step} />
              ))}
              {trace.isActive && (
                <div className="flex min-h-9 items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                  正在继续处理
                </div>
              )}
            </div>
          ) : (
            <div className="max-h-80 overflow-y-auto">
              {orchestration && orchestration.layers.length > 0 && (
                <div className="border-b p-3">
                  <OrchestrationPanel orchestration={orchestration} />
                </div>
              )}
              {trace.steps.map((step, index) => (
                <TechnicalStep key={`${index}-${step.timestamp}`} step={step} index={index} />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
