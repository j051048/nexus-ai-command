import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';
import { GitMerge } from 'lucide-react';
import { WorkflowNodeShell } from './WorkflowNodeShell';

export interface SubWorkflowNodeData {
  label: string;
  workflow_id: string;
  workflow_name: string;
  [key: string]: unknown;
}

function SubWorkflowNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as SubWorkflowNodeData;

  return (
    <WorkflowNodeShell selected={selected} icon={GitMerge} typeLabel="子流程" title={nodeData.label || '子流程'} tone="info">
      <div className="flex items-center justify-between gap-3 text-[11px]"><span className="text-muted-foreground">引用</span><span className="max-w-28 truncate font-medium">{nodeData.workflow_name || '未选择'}</span></div>
    </WorkflowNodeShell>
  );
}

export const SubWorkflowNode = memo(SubWorkflowNodeComponent);
