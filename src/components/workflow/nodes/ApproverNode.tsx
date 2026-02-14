import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { UserCheck } from 'lucide-react';

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
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-background shadow-sm min-w-[160px]
        ${selected ? 'border-primary ring-2 ring-primary/20' : 'border-blue-400'}
        transition-all
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-blue-500 !border-2 !border-background"
      />

      <div className="flex items-center gap-2 mb-1">
        <div className="p-1.5 rounded-md bg-blue-500/10">
          <UserCheck className="w-4 h-4 text-blue-500" />
        </div>
        <span className="text-xs font-medium text-blue-600">审批节点</span>
      </div>

      <div className="text-sm font-semibold">{nodeData.label || '审批人'}</div>
      <div className="text-xs text-muted-foreground mt-0.5">
        角色: {roleLabel}
      </div>
      {nodeData.timeout_hours > 0 && (
        <div className="text-xs text-muted-foreground">
          超时: {nodeData.timeout_hours}小时
        </div>
      )}
      {nodeData.can_delegate && (
        <div className="text-xs text-blue-500 mt-0.5">可委托</div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-blue-500 !border-2 !border-background"
      />
    </div>
  );
}

export const ApproverNode = memo(ApproverNodeComponent);
