import { useState, useEffect } from 'react';
import { supabase } from '@/lib/supabase';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { Shield, Search } from 'lucide-react';

interface User {
  id: string;
  name: string;
  email: string;
  department: string | null;
  role: 'employee' | 'manager' | 'boss';
}

const roleColors = {
  boss: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  manager: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  employee: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
};

const roleLabels = {
  boss: '老板',
  manager: '经理',
  employee: '员工',
};

export default function RoleManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [filteredUsers, setFilteredUsers] = useState<User[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState<string>('all');
  const [departments, setDepartments] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  // 加载用户数据
  useEffect(() => {
    fetchUsers();
  }, []);

  // 过滤用户
  useEffect(() => {
    let filtered = users;

    // 按搜索词过滤
    if (searchTerm) {
      filtered = filtered.filter(
        (user) =>
          user.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          user.email.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // 按部门过滤
    if (departmentFilter !== 'all') {
      filtered = filtered.filter((user) => user.department === departmentFilter);
    }

    setFilteredUsers(filtered);
  }, [searchTerm, departmentFilter, users]);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const { data, error } = await supabase
        .from('users')
        .select('id, name, email, department, role')
        .order('name');

      if (error) throw error;

      setUsers(data || []);
      setFilteredUsers(data || []);

      // 提取唯一部门列表
      const uniqueDepts = Array.from(
        new Set(data?.map((u) => u.department).filter(Boolean) || [])
      ) as string[];
      setDepartments(uniqueDepts);
    } catch (error) {
      console.error('Error fetching users:', error);
      toast({
        title: '加载失败',
        description: '无法加载用户列表',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = async (userId: string, newRole: 'employee' | 'manager' | 'boss') => {
    try {
      const { error } = await supabase
        .from('users')
        .update({ role: newRole })
        .eq('id', userId);

      if (error) throw error;

      // 更新本地状态
      setUsers((prev) =>
        prev.map((user) => (user.id === userId ? { ...user, role: newRole } : user))
      );

      toast({
        title: '角色已更新',
        description: `已成功将角色修改为 ${roleLabels[newRole]}`,
      });
    } catch (error) {
      console.error('Error updating role:', error);
      toast({
        title: '更新失败',
        description: '无法更新用户角色',
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex items-center gap-3">
        <Shield className="w-8 h-8 text-primary" />
        <div>
          <h1 className="text-3xl font-bold">角色管理</h1>
          <p className="text-muted-foreground">管理员工的系统角色与权限</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>员工角色列表</CardTitle>
        </CardHeader>
        <CardContent>
          {/* 搜索和筛选 */}
          <div className="flex flex-col md:flex-row gap-4 mb-6">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="按姓名或邮箱搜索..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={departmentFilter} onValueChange={setDepartmentFilter}>
              <SelectTrigger className="w-full md:w-[200px]">
                <SelectValue placeholder="筛选部门" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">所有部门</SelectItem>
                {departments.map((dept) => (
                  <SelectItem key={dept} value={dept}>
                    {dept}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 用户表格 */}
          {loading ? (
            <div className="flex justify-center items-center py-12">
              <div className="animate-spin w-8 h-8 border-4 border-primary border-t-transparent rounded-full" />
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>姓名</TableHead>
                    <TableHead>邮箱</TableHead>
                    <TableHead>部门</TableHead>
                    <TableHead>当前角色</TableHead>
                    <TableHead className="w-[200px]">修改角色</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        没有找到符合条件的用户
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredUsers.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell className="font-medium">{user.name}</TableCell>
                        <TableCell>{user.email}</TableCell>
                        <TableCell>{user.department || '未分配'}</TableCell>
                        <TableCell>
                          <Badge className={roleColors[user.role]}>
                            {roleLabels[user.role]}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Select
                            value={user.role}
                            onValueChange={(value) =>
                              handleRoleChange(user.id, value as 'employee' | 'manager' | 'boss')
                            }
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="employee">员工</SelectItem>
                              <SelectItem value="manager">经理</SelectItem>
                              <SelectItem value="boss">老板</SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
