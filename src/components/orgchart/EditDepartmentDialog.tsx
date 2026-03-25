import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2, UserCog, UserPlus, Trash2 } from 'lucide-react';
import { 
  useUpdateDepartment, 
  useDeleteDepartment, 
  useOrgMembers,
  type OrgDepartment 
} from '@/hooks/useOrgChart';

interface EditDepartmentDialogProps {
  deptId: string | null;
  onOpenChange: (open: boolean) => void;
  departments: OrgDepartment[];
}

export function EditDepartmentDialog({ deptId, onOpenChange, departments }: EditDepartmentDialogProps) {
  const currentDept = departments.find(d => d.id === deptId);
  const [name, setName] = useState('');
  const [managerId, setManagerId] = useState<string>('__none__');
  const [parentId, setParentId] = useState<string>('__none__');
  
  const { data: members = [] } = useOrgMembers();
  const updateDept = useUpdateDepartment();
  const deleteDept = useDeleteDepartment();

  useEffect(() => {
    if (currentDept) {
      setName(currentDept.name);
      setManagerId(currentDept.manager_id || '__none__');
      setParentId(currentDept.parent_id || '__none__');
    }
  }, [currentDept]);

  const handleSubmit = async () => {
    if (!deptId || !name.trim()) return;
    await updateDept.mutateAsync({
      deptId,
      name: name.trim(),
      managerId: managerId === '__none__' ? null : managerId,
      parentId: parentId === '__none__' ? null : parentId,
    });
    onOpenChange(false);
  };

  const handleDelete = async () => {
    if (!deptId) return;
    if (confirm('确定要删除该部门吗？下属部门和人员将失去归属。')) {
      await deleteDept.mutateAsync(deptId);
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={!!deptId} onOpenChange={(o) => !o && onOpenChange(false)}>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserCog className="w-5 h-5 text-primary" />
            编辑部门「{currentDept?.name}」
          </DialogTitle>
          <DialogDescription>修改部门名称、负责人及层级关系</DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 pt-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">部门名称</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="请输入部门名称"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center justify-between">
              部门负责人
              <span className="text-[10px] text-muted-foreground font-normal">指定该部门的管理人员</span>
            </label>
            <Select value={managerId} onValueChange={setManagerId}>
              <SelectTrigger>
                <SelectValue placeholder="选择负责人" />
              </SelectTrigger>
              <SelectContent className="max-h-[200px]">
                <SelectItem value="__none__">无负责人</SelectItem>
                {members.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.full_name} ({m.role})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">上级部门</label>
            <Select value={parentId} onValueChange={setParentId}>
              <SelectTrigger>
                <SelectValue placeholder="选择上级部门" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">无上级（顶级部门）</SelectItem>
                {departments
                  .filter(d => d.id !== deptId)
                  .map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.name}
                    </SelectItem>
                  ))
                }
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-border mt-4">
            <Button 
              variant="ghost" 
              className="text-destructive hover:text-destructive hover:bg-destructive/10"
              onClick={handleDelete}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              删除部门
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                取消
              </Button>
              <Button onClick={handleSubmit} disabled={updateDept.isPending}>
                {updateDept.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                保存修改
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
