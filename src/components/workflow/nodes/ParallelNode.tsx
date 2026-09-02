import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';
import { Users } from 'lucide-react';
import { WorkflowNodeShell } from './WorkflowNodeShell';

export interface ParallelNodeData {
  label: string;
  parallel_count: number;
  [key: string]: unknown;
}

function ParallelNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as ParallelNodeData;
  const count = nodeData.parallel_count || 2;

  return (
    <WorkflowNodeShell selected={selected} icon={Users} typeLabel="并行审批" title={nodeData.label || '并行审批'} tone="info">
      <div className="flex items-center justify-between text-[11px]"><span className="text-muted-foreground">并行分支</span><span className="font-medium tabular-nums">{count} 路</span></div>
    </WorkflowNodeShell>
  );
}

export const ParallelNode = memo(ParallelNodeComponent);
