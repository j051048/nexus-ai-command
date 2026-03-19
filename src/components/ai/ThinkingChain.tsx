import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Brain,
  Wrench,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Loader2,
  MessageSquare,
  Sparkles,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export interface ThinkingStep {
  phase: 'planning' | 'executing' | 'reflecting' | 'responding';
  content: string;
  tool_name?: string;
  tool_args?: Record<string, unknown>;
  tool_result?: string;
  timestamp: number;
  duration_ms?: number;
}

interface ThinkingChainProps {
  steps: ThinkingStep[];
  isComplete?: boolean;
  isStreaming?: boolean;
  className?: string;
}

const phaseConfig = {
  planning: {
    icon: Brain,
    label: '规划',
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
  },
  executing: {
    icon: Wrench,
    label: '执行',
    color: 'text-amber-500',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/30',
  },
  reflecting: {
    icon: Sparkles,
    label: '反思',
    color: 'text-purple-500',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500/30',
  },
  responding: {
    icon: MessageSquare,
    label: '回复',
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
    borderColor: 'border-green-500/30',
  },
};

function ThinkingStepItem({
  step,
  isLast,
  isActive
}: {
  step: ThinkingStep;
  isLast: boolean;
  isActive: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const config = phaseConfig[step.phase] || phaseConfig.planning;
  const Icon = config.icon;

  const hasDetails = step.tool_name || step.tool_result;

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
      className="relative"
    >
      {/* Connection line */}
      {!isLast && (
        <div className="absolute left-4 top-8 w-0.5 h-full -ml-px bg-border" />
      )}

      <div className="flex gap-3">
        {/* Icon */}
        <div
          className={cn(
            'w-8 h-8 rounded-full flex items-center justify-center shrink-0 border',
            config.bgColor,
            config.borderColor
          )}
        >
          {isActive ? (
            <Loader2 className={cn('w-4 h-4 animate-spin', config.color)} />
          ) : (
            <Icon className={cn('w-4 h-4', config.color)} />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 pb-4">
          <div
            className={cn(
              'flex items-center gap-2 cursor-pointer',
              hasDetails && 'hover:opacity-80'
            )}
            onClick={() => hasDetails && setIsExpanded(!isExpanded)}
          >
            <span className={cn('text-xs font-medium uppercase', config.color)}>
              {config.label}
            </span>
            {step.duration_ms && (
              <span className="text-xs text-muted-foreground">
                {step.duration_ms}ms
              </span>
            )}
            {hasDetails && (
              isExpanded ? (
                <ChevronDown className="w-3 h-3 text-muted-foreground" />
              ) : (
                <ChevronRight className="w-3 h-3 text-muted-foreground" />
              )
            )}
          </div>

          <p className="text-sm text-foreground/80 mt-0.5">
            {step.content}
          </p>

          {/* Tool details (expandable) */}
          <AnimatePresence>
            {isExpanded && hasDetails && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="mt-2 p-3 rounded-lg bg-muted/50 text-xs space-y-2">
                  {step.tool_name && (
                    <div>
                      <span className="text-muted-foreground">工具: </span>
                      <code className="font-mono text-primary">{step.tool_name}</code>
                    </div>
                  )}
                  {step.tool_args && (
                    <div>
                      <span className="text-muted-foreground">参数: </span>
                      <pre className="mt-1 p-2 rounded bg-background/50 overflow-x-auto">
                        {JSON.stringify(step.tool_args, null, 2)}
                      </pre>
                    </div>
                  )}
                  {step.tool_result && (
                    <div>
                      <span className="text-muted-foreground">结果: </span>
                      <pre className="mt-1 p-2 rounded bg-background/50 overflow-x-auto max-h-32 overflow-y-auto">
                        {step.tool_result}
                      </pre>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}

export function ThinkingChain({
  steps,
  isComplete,
  isStreaming,
  className
}: ThinkingChainProps) {
  const [isCollapsed, setIsCollapsed] = useState(true);

  if (!steps || steps.length === 0) {
    return null;
  }

  // Calculate total duration from first step to last step
  const totalDuration = steps.length > 1
    ? steps[steps.length - 1].timestamp - steps[0].timestamp
    : steps[0].duration_ms || 0;

  // Compute per-step duration from timestamps if duration_ms not set
  const stepsWithDuration = steps.map((step, i) => {
    if (step.duration_ms) return step;
    if (i < steps.length - 1) {
      return { ...step, duration_ms: steps[i + 1].timestamp - step.timestamp };
    }
    return step;
  });

  // Summary line for collapsed state
  const lastStep = steps[steps.length - 1];
  const summaryText = isStreaming
    ? `${phaseConfig[lastStep.phase]?.label || '处理'}中...`
    : `${steps.length} 步完成`;

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <div className={cn('rounded-lg border bg-card/50 overflow-hidden', className)}>
      {/* Header */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="w-full px-4 py-2.5 flex items-center justify-between hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium">思考过程</span>
          <span className="text-xs text-muted-foreground">
            {summaryText}
          </span>
          {totalDuration > 0 && (
            <span className="text-xs text-muted-foreground/70 font-mono">
              {formatDuration(totalDuration)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isStreaming && (
            <Loader2 className="w-3 h-3 animate-spin text-primary" />
          )}
          {isComplete && (
            <CheckCircle2 className="w-4 h-4 text-green-500" />
          )}
          {isCollapsed ? (
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {/* Collapsed summary: show phase badges */}
      {isCollapsed && (
        <div className="px-4 pb-2.5 flex flex-wrap gap-1.5">
          {stepsWithDuration.map((step, i) => {
            const config = phaseConfig[step.phase] || phaseConfig.planning;
            const Icon = config.icon;
            const isActive = isStreaming && i === steps.length - 1;
            return (
              <span
                key={`${step.timestamp}-${i}`}
                className={cn(
                  'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border',
                  config.bgColor, config.borderColor, config.color,
                )}
              >
                {isActive ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Icon className="w-3 h-3" />
                )}
                {step.tool_name || config.label}
                {step.duration_ms ? ` ${formatDuration(step.duration_ms)}` : ''}
              </span>
            );
          })}
        </div>
      )}

      {/* Steps (expanded) */}
      <AnimatePresence>
        {!isCollapsed && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 pt-2">
              {stepsWithDuration.map((step, index) => (
                <ThinkingStepItem
                  key={`${step.timestamp}-${index}`}
                  step={step}
                  isLast={index === stepsWithDuration.length - 1}
                  isActive={isStreaming && index === stepsWithDuration.length - 1}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default ThinkingChain;
