/**
 * OrgChartPage - 组织架构管理页面
 * Tab 1: 可视化架构图（ReactFlow 树形图 + 拖拽编辑）
 * Tab 2: 部门管理（层级化树形列表 + CRUD）
 * Tab 3: 成员列表（完整员工管理：编辑/删除/转移/详情）
 */

import React, { useState, useMemo } from 'react';
import {
  Users,
  Edit2,
  Loader2,
  Search,
  UserCheck,
  X,
  Building2,
  Network,
  List,
  Plus,
  Trash2,
  ChevronRight,
  FolderTree,
  Pencil,
  ArrowRightLeft,
  UserMinus,
  AlertTriangle,
  BarChart3,
  Award,
  FileCheck,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { toast } from 'sonner';
import { useOrgMembers, useUpdateManager, useDepartments, useDeleteDepartment, type OrgMember, type OrgDepartment } from '@/hooks/useOrgChart';
import {
  useAllEmployees,
  useUpdateEmployee,
  useDeleteEmployee,
  useTransferEmployeeData,
  useEmployeeStats,
  useDepartments as useEmpDepartments,
  type Employee,
} from '@/hooks/useEmployeeManagement';
import { useAuth } from '@/components/auth/AuthContext';
import { ReactFlowProvider } from '@xyflow/react';
import { OrgFlowCanvas } from '@/components/orgchart/OrgFlowCanvas';
import { EditDepartmentDialog } from '@/components/orgchart/EditDepartmentDialog';
import { AddDepartmentDialog } from '@/components/orgchart/AddDepartmentDialog';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { EmployeeDetail } from '@/components/admin/EmployeeDetail';

// ─── Role Display ───────────────────────────────────────────

const ROLE_LABELS: Record<string, string> = {
  boss: '管理员',
  founder: '创始人',
  manager: '经理',
  admin: '系统管理员',
  employee: '员工',
  ai_assistant: 'AI助手',
};

function getRoleLabel(role: unknown) {
  const r = safeStr(role);
  return ROLE_LABELS[r] || r;
}

// 安全提取字符串值（全局复用，防止字段是对象时崩溃）
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

function getRoleBadgeColor(role: unknown) {
  const r = safeStr(role);
  switch (r) {
    case 'boss':
    case 'founder':
      return 'bg-amber-500/10 text-amber-600 border-amber-500/20';
    case 'manager':
      return 'bg-blue-500/10 text-blue-600 border-blue-500/20';
    case 'admin':
      return 'bg-purple-500/10 text-purple-600 border-purple-500/20';
    case 'ai_assistant':
      return 'bg-purple-500/10 text-purple-500 border-purple-500/20';
    default:
      return 'bg-muted text-muted-foreground border-border';
  }
}

// ─── Employee Stats Preview ─────────────────────────────────

function EmployeeStatsPreview({ userId }: { userId: string }) {
  const { data: stats, isLoading } = useEmployeeStats(userId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-3 gap-4 py-4">
      <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50">
        <BarChart3 className="w-5 h-5 text-primary" />
        <div>
          <p className="text-sm font-medium text-foreground">{stats?.metricsCount || 0}</p>
          <p className="text-xs text-muted-foreground">业绩记录</p>
        </div>
      </div>
      <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50">
        <Award className="w-5 h-5 text-gold" />
        <div>
          <p className="text-sm font-medium text-foreground">{stats?.badgesCount || 0}</p>
          <p className="text-xs text-muted-foreground">徽章</p>
        </div>
      </div>
      <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50">
        <FileCheck className="w-5 h-5 text-success" />
        <div>
          <p className="text-sm font-medium text-foreground">{stats?.approvalsCount || 0}</p>
          <p className="text-xs text-muted-foreground">审批记录</p>
        </div>
      </div>
    </div>
  );
}

// ─── Edit Manager Modal ─────────────────────────────────────

interface EditManagerModalProps {
  member: OrgMember;
  allMembers: OrgMember[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (userId: string, managerId: string | null) => void;
  isSaving: boolean;
}

function EditManagerModal({
  member,
  allMembers,
  open,
  onOpenChange,
  onSave,
  isSaving,
}: EditManagerModalProps) {
  const [selectedManagerId, setSelectedManagerId] = useState<string>(
    member.manager_id || '__none__'
  );

  const managerOptions = allMembers.filter((m) => m.id !== member.id);

  const handleSave = () => {
    const managerId = selectedManagerId === '__none__' ? null : selectedManagerId;
    onSave(member.id, managerId);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>编辑汇报关系</DialogTitle>
          <DialogDescription>
           设置 <span className="font-medium text-foreground">{safeStr(member.full_name)}</span> 的直属上级
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="p-3 rounded-lg bg-secondary/30 border border-border/50">
            <div className="text-sm">
              <span className="text-muted-foreground">员工：</span>
              <span className="font-medium">{safeStr(member.full_name)}</span>
            </div>
            <div className="text-sm mt-1">
              <span className="text-muted-foreground">部门：</span>
              <span>{safeStr(member.department) || '未分配'}</span>
            </div>
            <div className="text-sm mt-1">
              <span className="text-muted-foreground">当前上级：</span>
              <span>{safeStr(member.manager_name) || '无'}</span>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">选择新上级</label>
            <Select
              value={selectedManagerId}
              onValueChange={setSelectedManagerId}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择上级" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">
                  <span className="text-muted-foreground">无上级</span>
                </SelectItem>
                {managerOptions.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    <div className="flex items-center gap-2">
                      <span>{safeStr(m.full_name)}</span>
                      {m.department && (
                        <span className="text-xs text-muted-foreground">({safeStr(m.department)})</span>
                      )}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <UserCheck className="w-4 h-4 mr-2" />
              )}
              保存
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ─── Member List View (full employee management) ─────────────

function OrgListView() {
  const { data: employees = [], isLoading } = useAllEmployees();
  const { data: orgMembers = [] } = useOrgMembers();
  const { data: empDepartments } = useEmpDepartments();
  const updateManager = useUpdateManager();
  const updateEmployee = useUpdateEmployee();
  const deleteEmployee = useDeleteEmployee();
  const transferData = useTransferEmployeeData();
  const { user, role } = useAuth();

  const isBossUser = role === 'boss' || role === 'founder';

  const [search, setSearch] = useState('');
  const [editingManager, setEditingManager] = useState<OrgMember | null>(null);
  const [viewingEmployee, setViewingEmployee] = useState<Employee | null>(null);

  // Edit employee dialog state
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [editForm, setEditForm] = useState({ employee_number: '', department: '', job_title: '', role: '' as string });

  // Delete dialog state
  const [deletingEmployee, setDeletingEmployee] = useState<Employee | null>(null);

  // Transfer dialog state
  const [transferringEmployee, setTransferringEmployee] = useState<Employee | null>(null);
  const [transferTargetId, setTransferTargetId] = useState<string>('');

  // Build manager_name lookup from orgMembers
  const managerNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const m of orgMembers) {
      if (m.manager_name) map.set(m.id, safeStr(m.manager_name));
    }
    return map;
  }, [orgMembers]);

  const filteredEmployees = useMemo(() => {
    if (!search.trim()) return employees;
    const lower = search.toLowerCase();
    return employees.filter(
      (e) =>
        e.name.toLowerCase().includes(lower) ||
        (e.department?.toLowerCase().includes(lower)) ||
        (e.job_title?.toLowerCase().includes(lower)) ||
        (e.employee_number?.toLowerCase().includes(lower))
    );
  }, [employees, search]);

  const handleManagerSave = async (userId: string, managerId: string | null) => {
    await updateManager.mutateAsync({ userId, managerId });
    setEditingManager(null);
  };

  const handleEditOpen = (emp: Employee) => {
    setEditingEmployee(emp);
    setEditForm({
      employee_number: emp.employee_number || '',
      department: emp.department || '',
      job_title: emp.job_title || '',
      role: emp.role || '',
    });
  };

  const handleEditSave = async () => {
    if (!editingEmployee) return;
    try {
      await updateEmployee.mutateAsync({
        userId: editingEmployee.user_id,
        updates: {
          employee_number: editForm.employee_number || null,
          department: editForm.department || null,
          job_title: editForm.job_title || null,
          role: (editForm.role || undefined) as Employee['role'] | undefined,
        },
      });
      toast.success(`员工 ${editingEmployee.name} 信息已更新`);
      setEditingEmployee(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误';
      toast.error('更新失败: ' + message);
    }
  };

  const handleDelete = async () => {
    if (!deletingEmployee) return;
    if (user && deletingEmployee.user_id === user.id) {
      toast.error('操作禁止：无法删除当前登录账号');
      setDeletingEmployee(null);
      return;
    }
    try {
      await deleteEmployee.mutateAsync(deletingEmployee.user_id);
      toast.success(`员工 ${deletingEmployee.name} 已删除`);
      setDeletingEmployee(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误';
      toast.error('删除失败: ' + message);
    }
  };

  const handleTransfer = async () => {
    if (!transferringEmployee || !transferTargetId) return;
    try {
      await transferData.mutateAsync({ fromUserId: transferringEmployee.user_id, toUserId: transferTargetId });
      const target = employees.find(e => e.user_id === transferTargetId);
      toast.success(`数据已从 ${transferringEmployee.name} 转移到 ${target?.name}`);
      setTransferringEmployee(null);
      setTransferTargetId('');
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误';
      toast.error('转移失败: ' + message);
    }
  };

  const handleTransferAndDelete = async () => {
    if (!transferringEmployee || !transferTargetId) return;
    try {
      await transferData.mutateAsync({ fromUserId: transferringEmployee.user_id, toUserId: transferTargetId });
      await deleteEmployee.mutateAsync(transferringEmployee.user_id);
      const target = employees.find(e => e.user_id === transferTargetId);
      toast.success(`数据已转移到 ${target?.name}，员工 ${transferringEmployee.name} 已删除`);
      setTransferringEmployee(null);
      setTransferTargetId('');
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误';
      toast.error('操作失败: ' + message);
    }
  };

  // If viewing detail, show EmployeeDetail component
  if (viewingEmployee) {
    return (
      <EmployeeDetail
        employee={viewingEmployee}
        allEmployees={employees}
        onBack={() => setViewingEmployee(null)}
        onDelete={async (id) => {
          try {
            await deleteEmployee.mutateAsync(id);
            toast.success('员工已删除');
            setViewingEmployee(null);
          } catch (error) {
            const message = error instanceof Error ? error.message : '未知错误';
            toast.error('删除失败: ' + message);
          }
        }}
        onTransfer={async (fromId, toId) => {
          try {
            await transferData.mutateAsync({ fromUserId: fromId, toUserId: toId });
            toast.success('数据已转移');
            setViewingEmployee(null);
          } catch (error) {
            const message = error instanceof Error ? error.message : '未知错误';
            toast.error('转移失败: ' + message);
          }
        }}
        onTransferAndDelete={async (fromId, toId) => {
          try {
            await transferData.mutateAsync({ fromUserId: fromId, toUserId: toId });
            await deleteEmployee.mutateAsync(fromId);
            toast.success('数据已转移且员工已删除');
            setViewingEmployee(null);
          } catch (error) {
            const message = error instanceof Error ? error.message : '未知错误';
            toast.error('操作失败: ' + message);
          }
        }}
        isProcessing={deleteEmployee.isPending || transferData.isPending}
      />
    );
  }

  const otherEmployees = (emp: Employee) => employees.filter(e => e.user_id !== emp.user_id && e.user_id !== user?.id);

  return (
    <>
      {/* Search */}
      <div className="relative max-w-md mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          placeholder="搜索姓名、部门、工号..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
        />
        {search && (
          <button
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => setSearch('')}
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="bg-card rounded-2xl border border-border shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <Loader2 className="w-10 h-10 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">正在加载组织成员...</p>
          </div>
        ) : filteredEmployees.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <Users className="w-16 h-16 mb-4 opacity-20" />
            <h3 className="text-lg font-medium text-foreground">
              {search ? '未找到匹配的成员' : '暂无成员数据'}
            </h3>
            <p className="text-sm mt-1">
              {search ? '请尝试其他搜索关键词' : '组织中还没有任何成员'}
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[180px]">姓名</TableHead>
                <TableHead className="w-[100px]">工号</TableHead>
                <TableHead>部门</TableHead>
                <TableHead>职务</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>直属上级</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEmployees.map((emp) => {
                const isSystem = emp.role === 'boss' || emp.role === 'ai_assistant';
                const orgMember = orgMembers.find(m => m.id === emp.user_id);
                const managerName = managerNameMap.get(emp.user_id);
                return (
                  <TableRow
                    key={emp.user_id}
                    className="cursor-pointer hover:bg-secondary/50"
                    onClick={() => setViewingEmployee(emp)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          "w-8 h-8 rounded-full flex items-center justify-center text-primary-foreground text-sm font-medium",
                          emp.role === 'ai_assistant' ? "bg-gradient-to-br from-purple-500 to-pink-500" : "bg-primary/80"
                        )}>
                          {emp.role === 'ai_assistant' ? '🤖' : emp.name.charAt(0)}
                        </div>
                        <span className="font-medium text-foreground">{emp.name}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-xs text-muted-foreground font-mono">{emp.employee_number || '-'}</span>
                    </TableCell>
                    <TableCell>
                      <span className="text-muted-foreground">{emp.department || '未分配'}</span>
                    </TableCell>
                    <TableCell>
                      <span className="text-muted-foreground">{emp.job_title || '-'}</span>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={cn('text-xs', getRoleBadgeColor(emp.role))}>
                        {getRoleLabel(emp.role)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {managerName ? (
                        <span className="text-foreground">{managerName}</span>
                      ) : (
                        <span className="text-muted-foreground/50">无</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-1">
                        {/* Edit manager relationship */}
                        {orgMember && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            title="编辑汇报关系"
                            onClick={() => setEditingManager(orgMember)}
                          >
                            <UserCheck className="w-4 h-4" />
                          </Button>
                        )}
                        {/* Edit employee info (boss only) */}
                        {isBossUser && !isSystem && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            title="编辑信息"
                            onClick={() => handleEditOpen(emp)}
                          >
                            <Pencil className="w-4 h-4" />
                          </Button>
                        )}
                        {/* Transfer data (boss only, non-system) */}
                        {isBossUser && !isSystem && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            title="数据转移"
                            onClick={() => { setTransferringEmployee(emp); setTransferTargetId(''); }}
                          >
                            <ArrowRightLeft className="w-4 h-4" />
                          </Button>
                        )}
                        {/* Delete (boss only, non-system, not self) */}
                        {isBossUser && !isSystem && emp.user_id !== user?.id && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive hover:text-destructive"
                            title="删除员工"
                            onClick={() => setDeletingEmployee(emp)}
                          >
                            <UserMinus className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>

      {/* Edit Manager Modal */}
      {editingManager && (
        <EditManagerModal
          member={editingManager}
          allMembers={orgMembers}
          open={!!editingManager}
          onOpenChange={(open) => !open && setEditingManager(null)}
          onSave={handleManagerSave}
          isSaving={updateManager.isPending}
        />
      )}

      {/* Edit Employee Dialog */}
      <Dialog open={!!editingEmployee} onOpenChange={(open) => !open && setEditingEmployee(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Pencil className="w-5 h-5 text-primary" />
              编辑员工信息
            </DialogTitle>
            <DialogDescription>
              修改 <strong>{editingEmployee?.name}</strong> 的角色、部门、工号和职务
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">角色</label>
              <Select value={editForm.role} onValueChange={(v) => setEditForm(p => ({ ...p, role: v }))}>
                <SelectTrigger><SelectValue placeholder="选择角色" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="employee">员工</SelectItem>
                  <SelectItem value="manager">经理</SelectItem>
                  <SelectItem value="boss">老板</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">部门</label>
              <Select value={editForm.department || '__none__'} onValueChange={(v) => setEditForm(p => ({ ...p, department: v === '__none__' ? '' : v }))}>
                <SelectTrigger><SelectValue placeholder="选择部门" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">未分配</SelectItem>
                  {empDepartments?.map((dept) => (
                    <SelectItem key={dept.id} value={dept.name}>{dept.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">工号</label>
              <Input placeholder="请输入工号，如 EMP001" value={editForm.employee_number} onChange={(e) => setEditForm(p => ({ ...p, employee_number: e.target.value }))} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">职务</label>
              <Input placeholder="请输入职务，如 高级工程师" value={editForm.job_title} onChange={(e) => setEditForm(p => ({ ...p, job_title: e.target.value }))} />
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" onClick={() => setEditingEmployee(null)}>取消</Button>
            <Button onClick={handleEditSave} disabled={updateEmployee.isPending}>
              {updateEmployee.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              保存
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deletingEmployee} onOpenChange={(open) => !open && setDeletingEmployee(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="w-5 h-5" />
              确认删除员工
            </DialogTitle>
            <DialogDescription>
              您即将删除员工 <strong>{deletingEmployee?.name}</strong>。此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          {deletingEmployee && <EmployeeStatsPreview userId={deletingEmployee.user_id} />}
          <div className="bg-warning/10 border border-warning/30 rounded-lg p-4 text-sm text-warning">
            <p className="font-medium mb-1">警告</p>
            <p>删除员工将导致其所有业绩数据、徽章和审批记录永久丢失。如需保留数据，请先进行数据转移。</p>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" onClick={() => setDeletingEmployee(null)}>取消</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteEmployee.isPending}>
              {deleteEmployee.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              确认删除
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Transfer Dialog */}
      <Dialog open={!!transferringEmployee} onOpenChange={(open) => !open && setTransferringEmployee(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ArrowRightLeft className="w-5 h-5 text-primary" />
              数据转移
            </DialogTitle>
            <DialogDescription>
              将员工 <strong>{transferringEmployee?.name}</strong> 的数据转移给其他员工
            </DialogDescription>
          </DialogHeader>
          {transferringEmployee && <EmployeeStatsPreview userId={transferringEmployee.user_id} />}
          <div className="space-y-4 mt-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">选择接收员工</label>
              <Select value={transferTargetId} onValueChange={setTransferTargetId}>
                <SelectTrigger><SelectValue placeholder="选择员工..." /></SelectTrigger>
                <SelectContent>
                  {transferringEmployee && otherEmployees(transferringEmployee).map((e) => (
                    <SelectItem key={e.user_id} value={e.user_id}>
                      {e.name} - {e.department || '无部门'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="bg-secondary/50 rounded-lg p-4 text-sm">
              <p className="font-medium text-foreground mb-2">将转移以下数据：</p>
              <ul className="list-disc list-inside text-muted-foreground space-y-1">
                <li>销售业绩记录</li>
                <li>获得的徽章</li>
                <li>审批申请记录</li>
              </ul>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" onClick={() => setTransferringEmployee(null)}>取消</Button>
            <Button variant="outline" onClick={handleTransfer} disabled={!transferTargetId || transferData.isPending}>
              {transferData.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              仅转移数据
            </Button>
            <Button variant="destructive" onClick={handleTransferAndDelete} disabled={!transferTargetId || transferData.isPending || deleteEmployee.isPending}>
              {(transferData.isPending || deleteEmployee.isPending) && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              转移并删除
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ─── Department Tree Helpers ──────────────────────────────────

interface FlatDept extends OrgDepartment {
  depth: number;
}

function flattenDeptTree(departments: OrgDepartment[]): FlatDept[] {
  const byParent = new Map<string | null, OrgDepartment[]>();
  for (const d of departments) {
    const key = d.parent_id || null;
    const list = byParent.get(key) || [];
    list.push(d);
    byParent.set(key, list);
  }
  const result: FlatDept[] = [];
  function walk(parentId: string | null, depth: number) {
    const children = (byParent.get(parentId) || []).sort((a, b) => a.sort_order - b.sort_order);
    for (const c of children) {
      result.push({ ...c, depth });
      walk(c.id, depth + 1);
    }
  }
  walk(null, 0);
  return result;
}

// ─── Department Management View ──────────────────────────────

function OrgDeptManageView() {
  const { data: departments = [], isLoading: deptsLoading } = useDepartments();
  const { data: members = [] } = useOrgMembers();
  const deleteDept = useDeleteDepartment();
  const { confirm, ConfirmDialogProps } = useConfirmDialog();
  const [search, setSearch] = useState('');
  const [editDeptId, setEditDeptId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  const flatDepts = useMemo(() => flattenDeptTree(departments), [departments]);

  const filtered = useMemo(() => {
    if (!search.trim()) return flatDepts;
    const lower = search.toLowerCase();
    return flatDepts.filter(d => safeStr(d.name).toLowerCase().includes(lower));
  }, [flatDepts, search]);

  // Count members per department (by name match)
  const memberCountMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const m of members) {
      const deptName = safeStr(m.department);
      if (deptName) {
        const dept = departments.find(d => safeStr(d.name) === deptName);
        if (dept) map.set(dept.id, (map.get(dept.id) || 0) + 1);
      }
    }
    return map;
  }, [members, departments]);

  const handleDelete = async (dept: FlatDept) => {
    const ok = await confirm({
      title: '确认删除部门',
      description: `确定要删除「${safeStr(dept.name)}」吗？该操作将解散此部门。`,
      variant: 'destructive',
    });
    if (ok) {
      await deleteDept.mutateAsync(dept.id);
    }
  };

  return (
    <>
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 mb-4">
        <div className="relative max-w-md flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="搜索部门名称..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
          {search && (
            <button
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              onClick={() => setSearch('')}
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        <Button onClick={() => setAddOpen(true)} size="sm">
          <Plus className="w-4 h-4 mr-1.5" />
          新建部门
        </Button>
      </div>

      <div className="bg-card rounded-2xl border border-border shadow-sm overflow-hidden">
        {deptsLoading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <Loader2 className="w-10 h-10 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">正在加载部门数据...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <FolderTree className="w-16 h-16 mb-4 opacity-20" />
            <h3 className="text-lg font-medium text-foreground">
              {search ? '未找到匹配的部门' : '暂无部门数据'}
            </h3>
            <p className="text-sm mt-1">
              {search ? '请尝试其他搜索关键词' : '可以在架构图中使用模板快速创建组织结构'}
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[320px]">部门名称</TableHead>
                <TableHead>负责人</TableHead>
                <TableHead className="w-[100px] text-center">成员数</TableHead>
                <TableHead className="w-[100px] text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((dept) => {
                const manager = members.find(m => m.id === dept.manager_id);
                const count = memberCountMap.get(dept.id) || 0;
                return (
                  <TableRow key={dept.id}>
                    <TableCell>
                      <div className="flex items-center gap-2" style={{ paddingLeft: dept.depth * 24 }}>
                        {dept.depth > 0 && (
                          <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/50 shrink-0" />
                        )}
                        <Building2 className="w-4 h-4 text-primary shrink-0" />
                        <span className="font-medium text-foreground">{safeStr(dept.name)}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      {manager ? (
                        <span className="text-foreground">{safeStr(manager.full_name)}</span>
                      ) : (
                        <span className="text-muted-foreground/50">未指定</span>
                      )}
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline" className="text-xs">
                        {count}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => setEditDeptId(dept.id)}
                        >
                          <Edit2 className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:text-destructive"
                          onClick={() => handleDelete(dept)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>

      {/* Dialogs */}
      <EditDepartmentDialog
        deptId={editDeptId}
        onOpenChange={(open) => !open && setEditDeptId(null)}
        departments={departments}
      />
      <AddDepartmentDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        departments={departments}
      />
      <ConfirmDialog {...ConfirmDialogProps} />
    </>
  );
}

// ─── Main Page ──────────────────────────────────────────────

export function OrgChartPage() {
  const { data: members = [] } = useOrgMembers();

  return (
    <div className="max-w-[1400px] mx-auto space-y-6 pb-20 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-3xl font-extrabold text-foreground tracking-tight flex items-center gap-3">
            <Building2 className="w-8 h-8 text-primary" />
            组织架构管理
          </h1>
          <p className="text-muted-foreground mt-2">
            可视化管理组织结构，拖拽调整部门层级和人员归属
          </p>
        </div>
        <Badge variant="outline" className="text-sm px-3 py-1">
          <Users className="w-4 h-4 mr-1.5" />
          共 {members.length} 人
        </Badge>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="chart" className="w-full">
        <TabsList>
          <TabsTrigger value="chart" className="gap-1.5">
            <Network className="w-4 h-4" />
            架构图
          </TabsTrigger>
          <TabsTrigger value="departments" className="gap-1.5">
            <FolderTree className="w-4 h-4" />
            部门管理
          </TabsTrigger>
          <TabsTrigger value="list" className="gap-1.5">
            <List className="w-4 h-4" />
            成员管理
          </TabsTrigger>
        </TabsList>

        <TabsContent value="chart" className="mt-4">
          <ReactFlowProvider>
            <OrgFlowCanvas />
          </ReactFlowProvider>
        </TabsContent>

        <TabsContent value="departments" className="mt-4">
          <OrgDeptManageView />
        </TabsContent>

        <TabsContent value="list" className="mt-4">
          <OrgListView />
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default OrgChartPage;
