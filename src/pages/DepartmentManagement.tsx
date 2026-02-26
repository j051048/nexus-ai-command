import { useState, useEffect, useCallback } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { useUser } from '@/contexts/UserContext';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { Building2, Plus, Pencil, Trash2, Users } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

interface Department {
  id: string;
  name: string;
  manager_id: string | null;
  created_at: string;
}

interface Manager {
  id: string;
  name: string;
}

interface DepartmentWithDetails extends Department {
  manager_name?: string;
  member_count?: number;
}

export default function DepartmentManagement() {
  const { user } = useUser();
  const [departments, setDepartments] = useState<DepartmentWithDetails[]>([]);
  const [managers, setManagers] = useState<Manager[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingDept, setEditingDept] = useState<DepartmentWithDetails | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [departmentToDelete, setDepartmentToDelete] = useState<string | null>(null);
  const [orgId, setOrgId] = useState<string | null>(null);
  
  const [formData, setFormData] = useState({
    name: '',
    manager_id: '',
  });

  const { toast } = useToast();

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);

      // 获取所有部门
      const { data: deptData, error: deptError } = await supabase.from('departments')
        .select('*')
        .order('name');

      if (deptError) throw deptError;

      // 获取所有经理和用户信息
      const { data: userData, error: userError } = await supabase.from('users')
        .select('id, name, role, department, organization_id');

      if (userError) throw userError;

      // 所有员工均可被指定为部门经理（排除 AI 助手）
      const managerList = userData?.filter((u) => u.role !== 'ai_assistant') || [];
      setManagers(managerList);

      // 获取当前用户的 organization_id
      if (user?.id) {
        const currentUser = userData?.find((u) => u.id === user.id);
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        if (currentUser && (currentUser as any).organization_id) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          setOrgId((currentUser as any).organization_id);
        }
      }

      // 为每个部门附加经理名称和成员数量
      const deptsWithDetails: DepartmentWithDetails[] = (deptData || []).map((dept) => {
        const manager = userData?.find((u) => u.id === dept.manager_id);
        const memberCount = userData?.filter((u) => u.department === dept.name).length || 0;

        return {
          ...dept,
          manager_name: manager?.name || '未指定',
          member_count: memberCount,
        };
      });

      setDepartments(deptsWithDetails);
    } catch (error) {
      toast({
        title: '加载失败',
        description: '无法加载部门数据',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [toast, user?.id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenDialog = (dept?: DepartmentWithDetails) => {
    if (dept) {
      setEditingDept(dept);
      setFormData({
        name: dept.name,
        manager_id: dept.manager_id || '',
      });
    } else {
      setEditingDept(null);
      setFormData({ name: '', manager_id: '' });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingDept(null);
    setFormData({ name: '', manager_id: '' });
  };

  const handleSaveDepartment = async () => {
    if (!formData.name.trim()) {
      toast({
        title: '请输入部门名称',
        variant: 'destructive',
      });
      return;
    }

    try {
      if (editingDept) {

        // 更新部门
        const managerId = formData.manager_id && formData.manager_id !== '__none__' ? formData.manager_id : null;
        const { error } = await supabase.from('departments')
          .update({
            name: formData.name,
            manager_id: managerId,
          })
          .eq('id', editingDept.id);

        if (error) throw error;

        toast({
          title: '部门已更新',
          description: `${formData.name} 部门信息已更新`,
        });
      } else {
        // 新建部门
        const managerId = formData.manager_id && formData.manager_id !== '__none__' ? formData.manager_id : null;
        const { error } = await supabase.from('departments').insert({
          name: formData.name,
          manager_id: managerId,
          organization_id: orgId,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } as any);

        if (error) throw error;

        toast({
          title: '部门已创建',
          description: `${formData.name} 部门已成功创建`,
        });
      }

      handleCloseDialog();
      fetchData();
    } catch (error) {
      toast({
        title: '保存失败',
        description: '无法保存部门信息',
        variant: 'destructive',
      });
    }
  };

  const handleDeleteDepartment = async () => {
    if (!departmentToDelete) return;

    try {
      const { error } = await supabase.from('departments')
        .delete()
        .eq('id', departmentToDelete);

      if (error) throw error;

      toast({
        title: '部门已删除',
        description: '部门已成功删除',
      });

      setDeleteDialogOpen(false);
      setDepartmentToDelete(null);
      fetchData();
    } catch (error) {
      toast({
        title: '删除失败',
        description: '无法删除部门',
        variant: 'destructive',
      });
    }
  };

  const openDeleteDialog = (deptId: string) => {
    setDepartmentToDelete(deptId);
    setDeleteDialogOpen(true);
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Building2 className="w-8 h-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">部门管理</h1>
            <p className="text-muted-foreground">管理公司部门和部门经理</p>
          </div>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="w-4 h-4 mr-2" />
          新建部门
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center items-center py-12">
          <div className="animate-spin w-8 h-8 border-4 border-primary border-t-transparent rounded-full" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {departments.length === 0 ? (
            <Card className="col-span-full">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Building2 className="w-12 h-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground text-center">
                  暂无部门，点击"新建部门"开始创建
                </p>
              </CardContent>
            </Card>
          ) : (
            departments.map((dept) => (
              <Card key={dept.id}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>{dept.name}</span>
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleOpenDialog(dept)}
                      >
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openDeleteDialog(dept.id)}
                      >
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </div>
                  </CardTitle>
                  <CardDescription>
                    部门经理：{dept.manager_name}
                  </CardDescription>
                </CardHeader>
                <CardFooter>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Users className="w-4 h-4" />
                    <span>{dept.member_count} 名成员</span>
                  </div>
                </CardFooter>
              </Card>
            ))
          )}
        </div>
      )}

      {/* 新建/编辑部门对话框 */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingDept ? '编辑部门' : '新建部门'}
            </DialogTitle>
            <DialogDescription>
              {editingDept
                ? '修改部门信息和部门经理'
                : '创建新部门并指定部门经理'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="dept-name">部门名称</Label>
              <Input
                id="dept-name"
                placeholder="请输入部门名称"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="dept-manager">部门经理</Label>
              <Select
                value={formData.manager_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, manager_id: value })
                }
              >
                <SelectTrigger id="dept-manager">
                  <SelectValue placeholder="选择部门经理" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">未指定</SelectItem>
                  {managers.map((mgr) => (
                    <SelectItem key={mgr.id} value={mgr.id}>
                      {mgr.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCloseDialog}>
              取消
            </Button>
            <Button onClick={handleSaveDepartment}>
              {editingDept ? '保存' : '创建'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 删除确认对话框 */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除部门？</AlertDialogTitle>
            <AlertDialogDescription>
              此操作无法撤销。部门删除后，该部门下的员工将不再关联此部门。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteDepartment}>
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
