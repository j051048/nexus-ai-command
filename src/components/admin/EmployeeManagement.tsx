import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Users,
  UserMinus,
  ArrowRightLeft,
  Loader2,
  Search,
  AlertTriangle,
  CheckCircle2,
  BarChart3,
  Award,
  FileCheck,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import {
  useAllEmployees,
  useTransferEmployeeData,
  useDeleteEmployee,
  useEmployeeStats,
  Employee,
} from '@/hooks/useEmployeeManagement';
import { useAuth } from '@/components/auth/AuthContext';

import { EmployeeDetail } from './EmployeeDetail';

interface EmployeeManagementProps {
  onProjectSelect?: (id: string) => void;
}

export function EmployeeManagement({ onProjectSelect }: EmployeeManagementProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null); // For dialogs
  const [viewingEmployee, setViewingEmployee] = useState<Employee | null>(null);   // For detail page
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showTransferDialog, setShowTransferDialog] = useState(false);
  const [transferTargetId, setTransferTargetId] = useState<string>('');

  const { data: employees, isLoading } = useAllEmployees();
  const transferData = useTransferEmployeeData();
  const deleteEmployee = useDeleteEmployee();
  const { user } = useAuth();

  // If viewing details, show detail component
  if (viewingEmployee) {
    return (
      <EmployeeDetail
        employee={viewingEmployee}
        allEmployees={employees || []}
        onBack={() => setViewingEmployee(null)}
        onProjectSelect={onProjectSelect}
        onDelete={async (id) => {
          try {
            await deleteEmployee.mutateAsync(id);
            toast.success('员工已删除');
            setViewingEmployee(null); // Go back to list
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

  const filteredEmployees = employees?.filter(e =>
    e.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    e.department?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const otherEmployees = employees?.filter(e =>
    e.user_id !== selectedEmployee?.user_id &&
    e.user_id !== user?.id
  );

  const handleDelete = async () => {
    if (!selectedEmployee) return;

    // Safety check: Prevent self-deletion
    if (user && selectedEmployee.user_id === user.id) {
      toast.error('操作禁止：无法删除当前登录账号');
      setShowDeleteDialog(false);
      return;
    }

    try {
      await deleteEmployee.mutateAsync(selectedEmployee.user_id);
      toast.success(`员工 ${selectedEmployee.name} 已删除`);
      setShowDeleteDialog(false);
      setSelectedEmployee(null);
    } catch (error: unknown) {
      const err = error as Error;
      toast.error('删除失败: ' + err.message);
    }
  };

  const handleTransfer = async () => {
    if (!selectedEmployee || !transferTargetId) return;

    try {
      await transferData.mutateAsync({
        fromUserId: selectedEmployee.user_id,
        toUserId: transferTargetId,
      });

      const targetEmployee = employees?.find(e => e.user_id === transferTargetId);
      toast.success(`数据已从 ${selectedEmployee.name} 转移到 ${targetEmployee?.name}`);
      setShowTransferDialog(false);
      setSelectedEmployee(null);
      setTransferTargetId('');
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误';
      toast.error('转移失败: ' + message);
    }
  };

  const handleTransferAndDelete = async () => {
    if (!selectedEmployee || !transferTargetId) return;

    try {
      // First transfer data
      await transferData.mutateAsync({
        fromUserId: selectedEmployee.user_id,
        toUserId: transferTargetId,
      });

      // Then delete employee
      await deleteEmployee.mutateAsync(selectedEmployee.user_id);

      const targetEmployee = employees?.find(e => e.user_id === transferTargetId);
      toast.success(`数据已转移到 ${targetEmployee?.name}，员工 ${selectedEmployee.name} 已删除`);
      setShowTransferDialog(false);
      setSelectedEmployee(null);
      setTransferTargetId('');
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误';
      toast.error('操作失败: ' + message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-foreground">员工管理</h2>
        <p className="text-sm text-muted-foreground mt-1">管理团队成员，处理离职员工数据交接</p>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          placeholder="搜索员工姓名或部门..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Employee List */}
      <div className="bg-card rounded-2xl p-6 border border-border">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : !filteredEmployees || filteredEmployees.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Users className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>没有找到员工</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredEmployees.map((employee) => (
              <EmployeeCard
                key={employee.id}
                employee={employee}
                onClick={() => setViewingEmployee(employee)}
                onDelete={() => {
                  setSelectedEmployee(employee);
                  setShowDeleteDialog(true);
                }}
                onTransfer={() => {
                  setSelectedEmployee(employee);
                  setShowTransferDialog(true);
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog (List View) */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="w-5 h-5" />
              确认删除员工
            </DialogTitle>
            <DialogDescription>
              您即将删除员工 <strong>{selectedEmployee?.name}</strong>。此操作不可撤销。
            </DialogDescription>
          </DialogHeader>

          {selectedEmployee && (
            <EmployeeStatsPreview userId={selectedEmployee.user_id} />
          )}

          <div className="bg-warning/10 border border-warning/30 rounded-lg p-4 text-sm text-warning">
            <p className="font-medium mb-1">警告</p>
            <p>删除员工将导致其所有业绩数据、徽章和审批记录永久丢失。如需保留数据，请先进行数据转移。</p>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteEmployee.isPending}
            >
              {deleteEmployee.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              确认删除
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Transfer Dialog (List View) */}
      <Dialog open={showTransferDialog} onOpenChange={setShowTransferDialog}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ArrowRightLeft className="w-5 h-5 text-primary" />
              数据转移
            </DialogTitle>
            <DialogDescription>
              将员工 <strong>{selectedEmployee?.name}</strong> 的数据转移给其他员工
            </DialogDescription>
          </DialogHeader>

          {selectedEmployee && (
            <EmployeeStatsPreview userId={selectedEmployee.user_id} />
          )}

          <div className="space-y-4 mt-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">选择接收员工</label>
              <Select value={transferTargetId} onValueChange={setTransferTargetId}>
                <SelectTrigger>
                  <SelectValue placeholder="选择员工..." />
                </SelectTrigger>
                <SelectContent>
                  {otherEmployees?.map((e) => (
                    <SelectItem key={e.user_id} value={e.user_id}>
                      {e.name} - {e.department}
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
            <Button variant="outline" onClick={() => setShowTransferDialog(false)}>
              取消
            </Button>
            <Button
              variant="outline"
              onClick={handleTransfer}
              disabled={!transferTargetId || transferData.isPending}
            >
              {transferData.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              仅转移数据
            </Button>
            <Button
              variant="destructive"
              onClick={handleTransferAndDelete}
              disabled={!transferTargetId || transferData.isPending || deleteEmployee.isPending}
            >
              {(transferData.isPending || deleteEmployee.isPending) && (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              )}
              转移并删除
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Employee Card Component
function EmployeeCard({
  employee,
  onClick,
  onDelete,
  onTransfer,
}: {
  employee: Employee;
  onClick: () => void;
  onDelete: () => void;
  onTransfer: () => void;
}) {
  const isBoss = employee.role === 'boss';
  const isAIAssistant = employee.role === 'ai_assistant';
  const isSystemUser = isBoss || isAIAssistant;

  // 获取角色显示名称和样式
  const getRoleBadge = () => {
    if (isBoss) {
      return { label: '老板', className: 'bg-gold/20 text-gold' };
    }
    if (isAIAssistant) {
      return { label: 'AI助手', className: 'bg-purple-500/20 text-purple-500' };
    }
    return { label: '员工', className: 'bg-primary/20 text-primary' };
  };

  const roleBadge = getRoleBadge();

  return (
    <div
      className="flex items-center justify-between p-4 rounded-xl bg-secondary/50 hover:bg-secondary transition-colors cursor-pointer group"
      onClick={onClick}
    >
      <div className="flex items-center gap-4">
        <div className={cn(
          "w-12 h-12 rounded-full flex items-center justify-center text-primary-foreground font-bold group-hover:scale-105 transition-transform",
          isAIAssistant ? "bg-gradient-to-br from-purple-500 to-pink-500" : "bg-gradient-primary"
        )}>
          {isAIAssistant ? '🤖' : employee.name.slice(0, 1)}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <p className="font-medium text-foreground group-hover:text-primary transition-colors">{employee.name}</p>
            <span className={cn("px-2 py-0.5 text-xs rounded-full", roleBadge.className)}>
              {roleBadge.label}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            {employee.department} · 积分 {employee.score} · 排名 #{employee.rank}
          </p>
        </div>
      </div>

      {/* 系统用户（老板和AI助手）不显示删除和转移按钮 */}
      {!isSystemUser && (
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <Button
            variant="outline"
            size="sm"
            onClick={onTransfer}
            className="flex items-center gap-2 hover:border-primary/50"
          >
            <ArrowRightLeft className="w-4 h-4" />
            数据转移
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onDelete}
            className="flex items-center gap-2 text-destructive hover:text-destructive hover:border-destructive/50"
          >
            <UserMinus className="w-4 h-4" />
            删除
          </Button>
        </div>
      )}
    </div>
  );
}

// Employee Stats Preview
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
