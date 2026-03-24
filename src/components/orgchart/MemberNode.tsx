import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export interface MemberNodeData {
  memberId: string;
  name: string;
  role: string;
  avatarUrl?: string | null;
  [key: string]: unknown;
}

const ROLE_LABELS: Record<string, string> = {
  boss: '管理员',
  founder: '创始人',
  manager: '经理',
  admin: '系统管理员',
  employee: '员工',
};

const ROLE_COLORS: Record<string, string> = {
  boss: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
  founder: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
  manager: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
  admin: 'bg-purple-500/10 text-purple-600 border-purple-500/20',
  employee: 'bg-muted text-muted-foreground border-border',
};

function MemberNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as MemberNodeData;

  return (
    <div
      className={cn(
        'px-3 py-2 rounded-lg border bg-card shadow-sm min-w-[160px] max-w-[180px] transition-all cursor-grab active:cursor-grabbing',
        selected
          ? 'border-primary ring-2 ring-primary/20'
          : 'border-border hover:border-primary/40'
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2.5 !h-2.5 !bg-muted-foreground !border-2 !border-background"
      />

      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center text-primary text-xs font-medium shrink-0">
          {d.avatarUrl ? (
            <img src={d.avatarUrl} className="w-full h-full rounded-full object-cover" alt="" />
          ) : (
            d.name.charAt(0)
          )}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground truncate">{d.name}</p>
          <Badge variant="outline" className={cn('text-[10px] px-1 py-0 h-4', ROLE_COLORS[d.role])}>
            {ROLE_LABELS[d.role] || d.role}
          </Badge>
        </div>
      </div>
    </div>
  );
}

export const MemberNode = memo(MemberNodeComponent);
