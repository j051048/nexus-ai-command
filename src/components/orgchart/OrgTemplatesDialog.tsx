import { 
  Building2, 
  Grid, 
  Layers, 
  Layout, 
  Network, 
  ArrowRight,
  Check,
  RefreshCcw,
  Loader2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useState } from 'react';
import { useCreateDepartment, useDepartments, useDeleteDepartment } from '@/hooks/useOrgChart';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

interface OrgTemplatesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const TEMPLATES = [
  {
    id: 'hierarchical',
    name: '层级型 (Hierarchical)',
    desc: '传统的自上而下管理模式，职责分明',
    icon: Layers,
    depts: [
      { name: '董事会', parent: null },
      { name: '总经理办公室', parent: '董事会' },
      { name: '财务部', parent: '总经理办公室' },
      { name: '人力资源部', parent: '总经理办公室' },
      { name: '行政部', parent: '总经理办公室' },
    ]
  },
  {
    id: 'functional',
    name: '职能型 (Functional)',
    desc: '按专业职能划分部门，效率优先',
    icon: Grid,
    depts: [
      { name: '总经理', parent: null },
      { name: '技术研发中心', parent: '总经理' },
      { name: '市场销售中心', parent: '总经理' },
      { name: '供应链管理中心', parent: '总经理' },
      { name: '客户服务中心', parent: '总经理' },
    ]
  },
  {
    id: 'divisional',
    name: '事业部型 (Divisional)',
    desc: '按产品、地区或客户划分独立经营单元',
    icon: Layout,
    depts: [
      { name: '集团总部', parent: null },
      { name: '生活电器事业部', parent: '集团总部' },
      { name: '智能通讯事业部', parent: '集团总部' },
      { name: '新能源事业部', parent: '集团总部' },
    ]
  },
  {
    id: 'matrix',
    name: '矩阵型 (Matrix)',
    desc: '职能部门与项目组交叉管理（模拟）',
    icon: Network,
    depts: [
      { name: '运营管理部', parent: null },
      { name: '研发部', parent: '运营管理部' },
      { name: '设计部', parent: '运营管理部' },
      { name: '项目一组 (跨部门)', parent: '研发部' },
      { name: '项目二组 (跨部门)', parent: '设计部' },
    ]
  },
  {
    id: 'flat',
    name: '扁平型 (Flat)',
    desc: '减少中层管理，强调快速响应和直接沟通',
    icon: Building2,
    depts: [
      { name: '创始团队', parent: null },
      { name: '核心开发组', parent: '创始团队' },
      { name: '核心增长组', parent: '创始团队' },
      { name: '核心支撑组', parent: '创始团队' },
    ]
  }
];

export function OrgTemplatesDialog({ open, onOpenChange }: OrgTemplatesDialogProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { data: existingDepts = [] } = useDepartments();
  const createDept = useCreateDepartment();
  const deleteDept = useDeleteDepartment();

  const handleApply = async () => {
    if (!selected) return;
    const template = TEMPLATES.find(t => t.id === selected);
    if (!template) return;

    setLoading(true);
    try {
      // 1. Cleanup existing structure
      if (existingDepts.length > 0) {
        if (!confirm('应用模板将保留现有人员但重组部门结构，是否继续？')) {
          setLoading(false);
          return;
        }
        // 逐个软删除，失败则中断
        for (const d of existingDepts) {
          await deleteDept.mutateAsync(d.id);
        }
      }

      // 2. Create new structure
      const createdMap = new Map<string, string>(); // name -> id

      for (const d of template.depts) {
        const parentId = d.parent ? createdMap.get(d.parent) : null;
        const res = await createDept.mutateAsync({
          name: d.name,
          parent_id: parentId
        });
        createdMap.set(d.name, res.id);
      }

      toast.success(`成功应用「${template.name}」模板`);
      onOpenChange(false);
    } catch (err) {
      console.error(err);
      toast.error('应用模板失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl bg-card border-border">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl font-bold">
            <Layout className="w-5 h-5 text-primary" />
            组织架构预设模板
          </DialogTitle>
          <DialogDescription>选择一个经典模板作为起点，随后可自由拖拽微调</DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-4 mt-4">
          {TEMPLATES.map((t) => {
            const Icon = t.icon;
            const isSelected = selected === t.id;
            return (
              <div
                key={t.id}
                onClick={() => setSelected(t.id)}
                className={cn(
                  "relative group cursor-pointer p-4 rounded-xl border-2 transition-all flex flex-col gap-3",
                  isSelected 
                    ? "border-primary bg-primary/5 ring-1 ring-primary/20" 
                    : "border-border hover:border-primary/40 hover:bg-primary/5"
                )}
              >
                <div className="flex items-center justify-between">
                  <div className={cn(
                    "p-2 rounded-lg shrink-0",
                    isSelected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground group-hover:text-primary"
                  )}>
                    <Icon className="w-5 h-5" />
                  </div>
                  {isSelected && <Check className="w-5 h-5 text-primary" />}
                </div>
                <div>
                  <h4 className="font-semibold text-sm">{t.name}</h4>
                  <p className="text-xs text-muted-foreground leading-relaxed mt-1">{t.desc}</p>
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex items-center justify-end gap-3 mt-8 pt-4 border-t border-border">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button 
            onClick={handleApply} 
            disabled={!selected || loading}
            className="min-w-[120px]"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <RefreshCcw className="w-4 h-4 mr-2" />
            )}
            应用模板
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
