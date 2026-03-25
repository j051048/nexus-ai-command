import { Building2, Plus, LayoutTemplate } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface OrgFlowToolbarProps {
  onAddDepartment: () => void;
  onShowTemplates: () => void;
}

export function OrgFlowToolbar({ onAddDepartment, onShowTemplates }: OrgFlowToolbarProps) {
  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card/80 backdrop-blur-sm">
      <p className="text-xs text-muted-foreground">
        拖拽人员节点到目标部门即可调动 | 滚轮滚轮缩放 | 按住拖拽平移
      </p>
      <div className="flex items-center gap-2">
        <Button 
          size="sm" 
          variant="outline" 
          onClick={onShowTemplates} 
          className="gap-1.5 h-8 border-primary/20 text-primary hover:bg-primary/5"
        >
          <LayoutTemplate className="w-3.5 h-3.5" />
          架构模板
        </Button>
        <Button size="sm" onClick={onAddDepartment} className="gap-1.5 h-8">
          <Plus className="w-3.5 h-3.5" />
          <Building2 className="w-3.5 h-3.5" />
          添加部门
        </Button>
      </div>
    </div>
  );
}
