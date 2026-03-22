import React from 'react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, Loader2, XCircle, AlertTriangle, Layers } from 'lucide-react';
import type { OrchestrationTrace } from '@/hooks/useOrchestrationTrace';

const AGENT_LABELS: Record<string, string> = {
  sales_agent: '销售顾问',
  content_agent: '内容策划',
  design_agent: '设计顾问',
  media_agent: '媒体投放',
  director_agent: '总监协调',
  data_agent: '数据分析',
  support_agent: '客服支持',
  market_agent: '市场研究',
  strategy_agent: '战略规划',
  product_agent: '产品顾问',
};

function getAgentLabel(code: string): string {
  return AGENT_LABELS[code] || code;
}

function TaskStatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />;
    case 'degraded':
      return <AlertTriangle className="w-3.5 h-3.5 text-yellow-500" />;
    case 'failed':
      return <XCircle className="w-3.5 h-3.5 text-red-500" />;
    case 'running':
      return <Loader2 className="w-3.5 h-3.5 text-blue-500 animate-spin" />;
    default:
      return <div className="w-3.5 h-3.5 rounded-full border-2 border-muted-foreground/30" />;
  }
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed': return 'border-green-500/30 bg-green-500/5';
    case 'degraded': return 'border-yellow-500/30 bg-yellow-500/5';
    case 'failed': return 'border-red-500/30 bg-red-500/5';
    case 'running': return 'border-blue-500/30 bg-blue-500/5';
    default: return 'border-border bg-muted/20';
  }
}

interface OrchestrationPanelProps {
  orchestration: OrchestrationTrace;
  className?: string;
}

export function OrchestrationPanel({ orchestration, className }: OrchestrationPanelProps) {
  if (orchestration.layers.length === 0) return null;

  const totalLayers = orchestration.layers[0]?.totalLayers ?? orchestration.layers.length;
  const finishedTasks = orchestration.completedCount + orchestration.failedCount;
  const progressPercent = orchestration.totalTasks > 0
    ? Math.round((finishedTasks / orchestration.totalTasks) * 100)
    : 0;

  return (
    <div className={cn('rounded-lg border border-border bg-card/50 p-3 space-y-3', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded bg-indigo-500/10 flex items-center justify-center">
            <Layers className="w-3 h-3 text-indigo-500" />
          </div>
          <span className="text-xs font-medium">多Agent编排</span>
          {orchestration.isActive && (
            <span className="flex items-center gap-1 text-[10px] text-indigo-500 animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
              执行中
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <span>{finishedTasks}/{orchestration.totalTasks} 完成</span>
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
            {totalLayers} 层
          </Badge>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            orchestration.failedCount > 0 ? 'bg-yellow-500' : 'bg-indigo-500'
          )}
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Layers */}
      <div className="space-y-2">
        {orchestration.layers.map((layer) => {
          const layerTasks = layer.tasks.map(t => {
            const task = orchestration.tasks.get(t.sub_task_id);
            return task ?? {
              subTaskId: t.sub_task_id,
              agentCode: t.agent_code,
              title: t.title,
              layerIdx: layer.layerIdx,
              status: 'pending' as const,
            };
          });

          return (
            <div key={layer.layerIdx} className="space-y-1">
              <span className="text-[10px] text-muted-foreground font-medium">
                第 {layer.layerIdx + 1} 层
              </span>
              <div className="flex flex-wrap gap-1.5">
                {layerTasks.map(task => (
                  <div
                    key={task.subTaskId}
                    className={cn(
                      'flex items-center gap-1.5 px-2 py-1 rounded-md border text-[11px] transition-all',
                      getStatusColor(task.status),
                      task.status === 'running' && 'ring-1 ring-blue-500/30'
                    )}
                  >
                    <TaskStatusIcon status={task.status} />
                    <span className="font-medium">{getAgentLabel(task.agentCode)}</span>
                    {task.durationMs && (
                      <span className="text-muted-foreground">
                        {(task.durationMs / 1000).toFixed(1)}s
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
