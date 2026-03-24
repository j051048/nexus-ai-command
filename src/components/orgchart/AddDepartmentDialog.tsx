import { useState } from 'react';
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
import { Loader2, Building2 } from 'lucide-react';
import { useCreateDepartment, type OrgDepartment } from '@/hooks/useOrgChart';

interface AddDepartmentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  departments: OrgDepartment[];
}

export function AddDepartmentDialog({ open, onOpenChange, departments }: AddDepartmentDialogProps) {
  const [name, setName] = useState('');
  const [parentId, setParentId] = useState<string>('__none__');
  const createDept = useCreateDepartment();

  const handleSubmit = async () => {
    if (!name.trim()) return;
    await createDept.mutateAsync({
      name: name.trim(),
      parent_id: parentId === '__none__' ? null : parentId,
    });
    setName('');
    setParentId('__none__');
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-primary" />
            添加部门
          </DialogTitle>
          <DialogDescription>创建新部门并指定上级部门</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-2">
            <label className="text-sm font-medium">部门名称</label>
            <Input
              placeholder="例如: 市场部"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">上级部门</label>
            <Select value={parentId} onValueChange={setParentId}>
              <SelectTrigger>
                <SelectValue placeholder="选择上级部门" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">
                  <span className="text-muted-foreground">无（顶级部门）</span>
                </SelectItem>
                {departments.map((d) => (
                  <SelectItem key={d.id} value={d.id}>
                    {d.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button onClick={handleSubmit} disabled={!name.trim() || createDept.isPending}>
              {createDept.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              创建
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
