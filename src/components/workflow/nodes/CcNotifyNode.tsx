import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Mail } from 'lucide-react';

export interface CcNotifyNodeData {
  label: string;
  recipients: string[];
  message: string;
  [key: string]: unknown;
}

function CcNotifyNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as CcNotifyNodeData;
  const recipients = nodeData.recipients || [];

  const recipientText = recipients.length > 0
    ? recipients.length > 2
      ? `${recipients.slice(0, 2).join('、')} 等${recipients.length}人`
      : recipients.join('、')
    : '未配置';

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-background shadow-sm min-w-[160px]
        ${selected ? 'border-teal-500 ring-2 ring-teal-500/20' : 'border-teal-400'}
        transition-all
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-teal-500 !border-2 !border-background"
      />

      <div className="flex items-center gap-2 mb-1">
        <div className="p-1.5 rounded-md bg-teal-500/10">
          <Mail className="w-4 h-4 text-teal-500" />
        </div>
        <span className="text-xs font-medium text-teal-600">抄送节点</span>
      </div>

      <div className="text-sm font-semibold">{nodeData.label || '抄送通知'}</div>
      <div className="text-xs text-muted-foreground mt-0.5">
        抄送: {recipientText}
      </div>
      {nodeData.message && (
        <div className="text-xs text-muted-foreground mt-0.5 truncate max-w-[140px]">
          消息: {nodeData.message}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-teal-500 !border-2 !border-background"
      />
    </div>
  );
}

export const CcNotifyNode = memo(CcNotifyNodeComponent);
