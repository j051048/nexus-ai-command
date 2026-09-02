import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';
import { UserCheck } from 'lucide-react';
import { WorkflowNodeShell } from './WorkflowNodeShell';

export interface ApproverNodeData {
  label: string;
  role: string;
  timeout_hours: number;
  can_delegate: boolean;
  [key: string]: unknown;
}

const ROLE_LABELS: Record<string, string> = {
  manager: '部门经理',
  director: '总监',
  cfo: 'CFO',
  ceo: 'CEO',
};

function ApproverNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as ApproverNodeData;
  const roleLabel = ROLE_LABELS[nodeData.role] || nodeData.role || '审批人';

  return (
    <WorkflowNodeShell selected={selected} icon={UserCheck} typeLabel="人工审批" title={nodeData.label || '审批人'} tone="primary">
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-muted-foreground">审批角色</span>
          <span className="font-medium">{roleLabel}</span>
        </div>
        {nodeData.timeout_hours > 0 && (
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-muted-foreground">处理时限</span>
            <span className="font-medium tabular-nums">{nodeData.timeout_hours} 小时</span>
          </div>
        )}
        {nodeData.can_delegate && (
          <div className="flex items-center justify-end">
            <span className="rounded-sm bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">允许委托</span>
          </div>
        )}
      </div>
    </WorkflowNodeShell>
  );
}

export const ApproverNode = memo(ApproverNodeComponent);
