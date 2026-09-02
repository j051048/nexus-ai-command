import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';
import { Timer } from 'lucide-react';
import { WorkflowNodeShell } from './WorkflowNodeShell';

export interface TimerNodeData {
  label: string;
  wait_hours: number;
  auto_advance: boolean;
  [key: string]: unknown;
}

function TimerNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as TimerNodeData;

  return (
    <WorkflowNodeShell selected={selected} icon={Timer} typeLabel="定时等待" title={nodeData.label || '定时等待'} tone="warning">
      <div className="flex items-center justify-between text-[11px]"><span className="text-muted-foreground">等待时间</span><span className="font-medium tabular-nums">{nodeData.wait_hours || 0} 小时</span></div>
      {nodeData.auto_advance && (
        <div className="mt-1 text-[11px] text-amber-700 dark:text-amber-300">超时后自动推进</div>
      )}
    </WorkflowNodeShell>
  );
}

export const TimerNode = memo(TimerNodeComponent);
