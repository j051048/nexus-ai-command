import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { Brain, Wrench, Sparkles, MessageSquare, ChevronDown, ChevronRight, ShieldCheck } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { ThinkingStep } from '../ThinkingChain';

interface ReasoningTraceProps {
  thinkingSteps: ThinkingStep[];
}

const phaseIcons = {
  planning: Brain,
  executing: Wrench,
  reflecting: Sparkles,
  responding: MessageSquare,
} as const;

const phaseColors = {
  planning: 'text-blue-500',
  executing: 'text-amber-500',
  reflecting: 'text-purple-500',
  responding: 'text-green-500',
} as const;

function formatDuration(ms: number) {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

export function ReasoningTrace({ thinkingSteps }: ReasoningTraceProps) {
  const [expanded, setExpanded] = useState(false);

  if (!thinkingSteps || thinkingSteps.length === 0) return null;

  // Compute per-step duration from timestamps if duration_ms not set
  const steps = thinkingSteps.map((step, i) => {
    if (step.duration_ms) return step;
    if (i < thinkingSteps.length - 1) {
      return { ...step, duration_ms: thinkingSteps[i + 1].timestamp - step.timestamp };
    }
    return step;
  });

  const totalMs =
    steps.length > 1
      ? steps[steps.length - 1].timestamp - steps[0].timestamp
      : steps[0].duration_ms || 0;
  const toolSteps = steps.filter((step) => step.tool_name);

  return (
    <div className="border-t border-border/50 bg-muted/30">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-1.5 px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <Brain className="w-3 h-3" />
        <span>查看推导链路</span>
        {totalMs > 0 && (
          <span className="font-mono text-[10px] opacity-70">{formatDuration(totalMs)}</span>
        )}
        <span className="ml-auto">
          {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        </span>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-2 space-y-1">
              <div className="mb-2 rounded-md border border-border/60 bg-background/70 p-2 text-[11px] text-muted-foreground">
                <div className="mb-1 flex items-center gap-1.5 font-medium text-foreground">
                  <ShieldCheck className="h-3 w-3 text-emerald-600" />
                  AI 操作透明度
                </div>
                <div>
                  已展示工具调用摘要、耗时和阶段。隐藏模型内部推理文本；涉及写入或高风险工具时由后端 HITL/RBAC 守卫确认。
                </div>
                {toolSteps.length > 0 && (
                  <div className="mt-1">
                    本次调用工具：{toolSteps.map((step) => step.tool_name).filter(Boolean).join('、')}
                  </div>
                )}
              </div>
              {steps.map((step, i) => {
                const Icon = phaseIcons[step.phase] || Brain;
                const color = phaseColors[step.phase] || 'text-muted-foreground';
                return (
                  <div key={`${step.timestamp}-${i}`} className="flex items-center gap-2 text-[11px]">
                    <Icon className={cn('w-3 h-3 shrink-0', color)} />
                    <span className={cn('font-medium', color)}>
                      {step.tool_name || step.phase}
                    </span>
                    {step.duration_ms && (
                      <span className="text-muted-foreground/60 font-mono">
                        {formatDuration(step.duration_ms)}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default ReasoningTrace;
