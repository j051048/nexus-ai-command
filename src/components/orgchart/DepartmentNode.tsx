import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Building2, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';

// 安全提取字符串值（防止 React #301）
function safeStr(v: unknown): string {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (typeof v === 'object') {
    const name = (v as Record<string, unknown>).name;
    if (typeof name === 'string') return name;
    return JSON.stringify(v);
  }
  return String(v);
}

export interface DepartmentNodeData {
  label: string;
  deptId: string;
  memberCount: number;
  managerName?: string;
  onAddMember?: (deptId: string) => void;
  [key: string]: unknown;
}

function DepartmentNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as DepartmentNodeData;
  const label = safeStr(d.label);
  const managerName = safeStr(d.managerName);
  const memberCount = typeof d.memberCount === 'number' ? d.memberCount : 0;

  return (
    <div
      className={cn(
        'px-4 py-3 rounded-xl border-2 bg-primary/5 dark:bg-primary/10 shadow-sm min-w-[200px] max-w-[220px] transition-all',
        selected
          ? 'border-primary ring-2 ring-primary/20'
          : 'border-primary/30 hover:border-primary/50'
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-primary !border-2 !border-background"
      />

      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="p-1.5 rounded-lg bg-primary/10 shrink-0">
            <Building2 className="w-4 h-4 text-primary" />
          </div>
          <span className="text-sm font-semibold text-foreground truncate">{label}</span>
        </div>
        {d.onAddMember && (
          <button
            className="p-1 rounded-md hover:bg-primary/10 text-primary/60 hover:text-primary transition-colors shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              d.onAddMember?.(safeStr(d.deptId));
            }}
            title="添加人员"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {managerName && (
        <p className="text-xs text-muted-foreground mt-1.5 truncate">
          负责人: {managerName}
        </p>
      )}
      <p className="text-xs text-muted-foreground/70 mt-0.5">{memberCount} 人</p>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-primary !border-2 !border-background"
      />
    </div>
  );
}

export const DepartmentNode = memo(DepartmentNodeComponent);
