/**
 * AgentTracePanel - AI Agent 执行日志面板
 * 可折叠面板，展示 Agent 的思考步骤、工具调用链和 Token 用量
 */

import React, { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import {
  ChevronDown,
  ChevronUp,
  Brain,
  Wrench,
  CheckCircle2,
  Zap,
  Clock,
  Code2,
  X,
  Activity,
  Loader2,
  XCircle,
  Play,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import type { AgentTrace, TraceStep } from '@/hooks/useAgentTrace';
import type { OrchestrationTrace } from '@/hooks/useOrchestrationTrace';
import { OrchestrationPanel } from './OrchestrationPanel';

// ─── Props ──────────────────────────────────────────────────

interface AgentTracePanelProps {
  trace: AgentTrace;
  className?: string;
  defaultExpanded?: boolean;
  onClose?: () => void;
  orchestration?: OrchestrationTrace;
}

// ─── Step Icon & Color ──────────────────────────────────────

function getStepIcon(type: TraceStep['type'], status?: TraceStep['status']) {
  switch (type) {
    case 'thinking':
      return <Brain className="w-3.5 h-3.5" />;
    case 'tool_call':
      return <Wrench className="w-3.5 h-3.5" />;
    case 'tool_result':
      return <CheckCircle2 className="w-3.5 h-3.5" />;
    case 'tool_progress':
      if (status === 'running') return <Loader2 className="w-3.5 h-3.5 animate-spin" />;
      if (status === 'error') return <XCircle className="w-3.5 h-3.5" />;
      return <CheckCircle2 className="w-3.5 h-3.5" />;
    default:
      return <Activity className="w-3.5 h-3.5" />;
  }
}

function getStepColor(type: TraceStep['type'], status?: TraceStep['status']) {
  switch (type) {
    case 'thinking':
      return 'text-blue-500 bg-blue-500/10 border-blue-500/20';
    case 'tool_call':
      return 'text-amber-500 bg-amber-500/10 border-amber-500/20';
    case 'tool_result':
      return 'text-green-500 bg-green-500/10 border-green-500/20';
    case 'tool_progress':
      if (status === 'error') return 'text-red-500 bg-red-500/10 border-red-500/20';
      if (status === 'success') return 'text-green-500 bg-green-500/10 border-green-500/20';
      return 'text-purple-500 bg-purple-500/10 border-purple-500/20';
    default:
      return 'text-muted-foreground bg-muted border-border';
  }
}

function getStepLabel(type: TraceStep['type']) {
  switch (type) {
    case 'thinking':
      return '思考';
    case 'tool_call':
      return '工具调用';
    case 'tool_result':
      return '执行结果';
    case 'tool_progress':
      return '工具执行';
    default:
      return '步骤';
  }
}

// ─── Step Component ─────────────────────────────────────────

function TraceStepItem({ step, index }: { step: TraceStep; index: number }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const hasExpandableContent = !!(step.args || (step.content && step.content.length > 120));

  return (
    <div className="relative pl-6">
      {/* Timeline connector */}
      <div className="absolute left-2 top-0 bottom-0 w-px bg-border" />
      <div
        className={cn(
          'absolute left-0 top-2 w-4 h-4 rounded-full flex items-center justify-center border',
          getStepColor(step.type, step.status)
        )}
      >
        {getStepIcon(step.type, step.status)}
      </div>

      <div className="pb-3 ml-2">
        <div
          className={cn(
            'rounded-lg border p-2.5 transition-colors',
            hasExpandableContent && 'cursor-pointer hover:bg-secondary/30',
            getStepColor(step.type, step.status).split(' ').slice(1).join(' ')
          )}
          onClick={hasExpandableContent ? () => setIsExpanded(!isExpanded) : undefined}
        >
          {/* Header */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <Badge
                variant="outline"
                className={cn('text-[10px] px-1.5 py-0 h-5 shrink-0', getStepColor(step.type, step.status))}
              >
                {getStepLabel(step.type)}
              </Badge>
              {step.name && (
                <code className="text-[11px] font-mono text-foreground/80 bg-muted px-1.5 py-0.5 rounded truncate">
                  {step.name}
                </code>
              )}
              {step.tokens && step.tokens > 0 && (
                <span className="text-[10px] text-muted-foreground flex items-center gap-0.5 shrink-0">
                  <Zap className="w-3 h-3" />
                  {step.tokens}
                </span>
              )}
              {step.duration_ms && step.duration_ms > 0 && (
                <span className="text-[10px] text-muted-foreground flex items-center gap-0.5 shrink-0">
                  <Clock className="w-3 h-3" />
                  {step.duration_ms}ms
                </span>
              )}
            </div>
            {hasExpandableContent && (
              <div className="text-muted-foreground shrink-0">
                {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </div>
            )}
          </div>

          {/* Content preview */}
          <p className="text-xs text-foreground/70 mt-1.5 leading-relaxed">
            {isExpanded || !hasExpandableContent
              ? step.content
              : step.content.slice(0, 120) + (step.content.length > 120 ? '...' : '')}
          </p>

          {/* Expanded: show args */}
          {isExpanded && step.args && (
            <div className="mt-2 p-2 rounded bg-muted/50 border border-border/50">
              <div className="flex items-center gap-1 mb-1">
                <Code2 className="w-3 h-3 text-muted-foreground" />
                <span className="text-[10px] text-muted-foreground font-medium">参数</span>
              </div>
              <pre className="text-[11px] font-mono text-foreground/80 whitespace-pre-wrap break-all max-h-40 overflow-auto">
                {step.args}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main Panel ─────────────────────────────────────────────

export function AgentTracePanel({
  trace,
  className,
  defaultExpanded = false,
  onClose,
  orchestration,
}: AgentTracePanelProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const stats = useMemo(() => {
    const thinkingCount = trace.steps.filter((s) => s.type === 'thinking').length;
    const toolCallCount = trace.steps.filter((s) => s.type === 'tool_call').length;
    const progressCount = trace.steps.filter((s) => s.type === 'tool_progress').length;
    const duration =
      trace.startTime && trace.endTime ? trace.endTime - trace.startTime : null;
    return { thinkingCount, toolCallCount, progressCount, duration };
  }, [trace]);

  // Don't render if no trace data
  if (trace.steps.length === 0 && !trace.isActive) {
    return null;
  }

  return (
    <div
      className={cn(
        'border border-border rounded-xl bg-card/95 backdrop-blur-sm shadow-sm overflow-hidden transition-all',
        className
      )}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-secondary/30 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-primary/10 flex items-center justify-center">
            <Activity className="w-3.5 h-3.5 text-primary" />
          </div>
          <span className="text-xs font-medium text-foreground">Agent 执行日志</span>
          {trace.isActive && (
            <span className="flex items-center gap-1 text-[10px] text-primary animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              执行中
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Stats badges */}
          {stats.thinkingCount > 0 && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 text-blue-500 border-blue-500/20">
              <Brain className="w-3 h-3 mr-0.5" />
              {stats.thinkingCount}
            </Badge>
          )}
          {stats.toolCallCount > 0 && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 text-amber-500 border-amber-500/20">
              <Wrench className="w-3 h-3 mr-0.5" />
              {stats.toolCallCount}
            </Badge>
          )}
          {stats.progressCount > 0 && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 text-purple-500 border-purple-500/20">
              <Play className="w-3 h-3 mr-0.5" />
              {stats.progressCount}
            </Badge>
          )}
          {trace.totalTokens > 0 && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 text-muted-foreground">
              <Zap className="w-3 h-3 mr-0.5" />
              {trace.totalTokens}
            </Badge>
          )}

          {onClose && (
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5"
              onClick={(e) => {
                e.stopPropagation();
                onClose();
              }}
            >
              <X className="w-3 h-3" />
            </Button>
          )}

          <div className="text-muted-foreground">
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </div>
      </div>

      {/* Expandable content */}
      {isExpanded && (
        <div className="border-t border-border">
          {/* P2-10: Orchestration panel */}
          {orchestration && orchestration.layers.length > 0 && (
            <div className="px-3 py-2 border-b border-border/50">
              <OrchestrationPanel orchestration={orchestration} />
            </div>
          )}

          {/* Summary bar */}
          {stats.duration && (
            <div className="px-3 py-1.5 bg-secondary/20 flex items-center gap-3 text-[10px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                总耗时 {(stats.duration / 1000).toFixed(1)}s
              </span>
              <span>|</span>
              <span>{trace.steps.length} 步骤</span>
              {trace.totalTokens > 0 && (
                <>
                  <span>|</span>
                  <span>{trace.totalTokens} tokens</span>
                </>
              )}
            </div>
          )}

          <div className="max-h-72 overflow-y-auto overscroll-contain">
            <div className="p-3 pt-2">
              {trace.steps.map((step, index) => (
                <TraceStepItem key={`${index}-${step.timestamp}`} step={step} index={index} />
              ))}
              {trace.isActive && (
                <div className="pl-6 relative">
                  <div className="absolute left-2 top-0 bottom-0 w-px bg-border" />
                  <div className="absolute left-0 top-2 w-4 h-4 rounded-full bg-primary/20 border border-primary/40 flex items-center justify-center animate-pulse">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                  </div>
                  <div className="ml-2 py-2">
                    <span className="text-xs text-muted-foreground animate-pulse">正在执行...</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
