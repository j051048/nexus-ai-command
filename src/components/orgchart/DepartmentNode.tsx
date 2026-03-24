import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Building2, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';

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
          <span className="text-sm font-semibold text-foreground truncate">{d.label}</span>
        </div>
        {d.onAddMember && (
          <button
            className="p-1 rounded-md hover:bg-primary/10 text-primary/60 hover:text-primary transition-colors shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              d.onAddMember?.(d.deptId);
            }}
            title="添加人员"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {d.managerName && (
        <p className="text-xs text-muted-foreground mt-1.5 truncate">
          负责人: {d.managerName}
        </p>
      )}
      <p className="text-xs text-muted-foreground/70 mt-0.5">{d.memberCount} 人</p>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-primary !border-2 !border-background"
      />
    </div>
  );
}

export const DepartmentNode = memo(DepartmentNodeComponent);
