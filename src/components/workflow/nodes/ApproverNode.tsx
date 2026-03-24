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
        px-4 py-3 rounded-xl border-2 bg-background/95 backdrop-blur-sm shadow-lg min-w-[190px]
        ${selected ? 'border-primary ring-4 ring-primary/20' : 'border-blue-400/50'}
        transition-all group
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-blue-500 !border-2 !border-background scale-110"
      />

      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 rounded-lg bg-blue-500/10">
          <UserCheck className="w-4 h-4 text-blue-600" />
        </div>
        <span className="text-[10px] font-bold text-blue-600 uppercase tracking-widest">审批节点</span>
      </div>

      <div className="text-sm font-bold tracking-tight mb-2">{nodeData.label || '审批人'}</div>
      
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-muted-foreground">审批角色</span>
          <span className="font-medium">{roleLabel}</span>
        </div>
        {nodeData.timeout_hours > 0 && (
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-muted-foreground">处理时限</span>
            <span className="font-medium text-orange-500">{nodeData.timeout_hours}h</span>
          </div>
        )}
        {nodeData.can_delegate && (
          <div className="flex items-center justify-end">
            <span className="px-1.5 py-0.5 rounded-md bg-blue-50 text-[9px] font-bold text-blue-600 dark:bg-blue-900/30">允许委托</span>
          </div>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-blue-500 !border-2 !border-background scale-110"
      />
    </div>
  );
}

export const ApproverNode = memo(ApproverNodeComponent);
