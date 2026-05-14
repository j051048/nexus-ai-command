import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ArrowLeft, Mail, Phone, Calendar, Award, BarChart3, FileCheck, Trash2, ArrowRightLeft, CheckCircle2, Plus, Pencil } from 'lucide-react';
import { Employee, useEmployeeStats, useUpdateEmployee, useDepartments } from '@/hooks/useEmployeeManagement';
import { useProjects } from '@/hooks/useProjects';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Loader2, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/components/auth/AuthContext';


interface EmployeeDetailProps {
    employee: Employee;
    allEmployees: Employee[];
    onBack: () => void;
    onDelete: (id: string) => void;
    onTransfer: (fromId: string, toId: string) => void;
    onTransferAndDelete: (fromId: string, toId: string) => void;
    onProjectSelect?: (id: string) => void;
    isProcessing: boolean;
}

export function EmployeeDetail({
    employee,
    allEmployees,
    onBack,
    onDelete,
    onTransfer,
    onTransferAndDelete,
    onProjectSelect,
    isProcessing
}: EmployeeDetailProps) {
    const { projects } = useProjects();
    const { data: stats } = useEmployeeStats(employee.user_id);
    const { data: departments } = useDepartments();
    const { role: authRole } = useAuth();
    const updateEmployee = useUpdateEmployee();
    const [showDeleteDialog, setShowDeleteDialog] = React.useState(false);
    const [showTransferDialog, setShowTransferDialog] = React.useState(false);
    const [showEditDialog, setShowEditDialog] = React.useState(false);
    const [transferTargetId, setTransferTargetId] = React.useState<string>('');
    const [selectedProjects, setSelectedProjects] = React.useState<string[]>([]);
    const [editForm, setEditForm] = React.useState({
        employee_number: employee.employee_number || '',
        department: employee.department || '',
        job_title: employee.job_title || '',
        role: employee.role || '' as string,
    });

    const isBossUser = authRole === 'boss';

    const toggleProjectSelection = (projectId: string) => {
        setSelectedProjects(prev =>
            prev.includes(projectId)
                ? prev.filter(id => id !== projectId)
                : [...prev, projectId]
        );
    };

    const otherEmployees = allEmployees.filter(e => e.user_id !== employee.user_id);
    const isBoss = employee.role === 'boss';
    const isAIAssistant = employee.role === 'ai_assistant';
    const isSystemUser = isBoss || isAIAssistant;

    const handleEditSave = async () => {
        try {
            await updateEmployee.mutateAsync({
                userId: employee.user_id,
                updates: {
                    employee_number: editForm.employee_number || null,
                    department: editForm.department || null,
                    job_title: editForm.job_title || null,
                    role: (editForm.role || undefined) as Employee['role'] | undefined,
                },
            });
            toast.success('员工信息已更新');
            setShowEditDialog(false);
        } catch (error) {
            const message = error instanceof Error ? error.message : '未知错误';
            toast.error('更新失败: ' + message);
        }
    };

    // 获取角色显示名称和样式
    const getRoleBadge = () => {
        if (isBoss) {
            return { label: '老板', className: 'bg-gold/20 text-gold' };
        }
        if (isAIAssistant) {
            return { label: 'AI助手 (二级权限)', className: 'bg-purple-500/20 text-purple-500' };
        }
        if (employee.role === 'manager') {
            return { label: '经理', className: 'bg-blue-500/20 text-blue-500' };
        }
        return { label: '员工', className: 'bg-primary/20 text-primary' };
    };
    const roleBadge = getRoleBadge();

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" onClick={onBack}>
                    <ArrowLeft className="w-5 h-5" />
                </Button>
                <div>
                    <h2 className="text-xl font-bold text-foreground">员工详情</h2>
                    <p className="text-sm text-muted-foreground">查看及管理员工详细信息</p>
                </div>
            </div>

            {/* Header Info */}
            <div className="bg-card rounded-2xl p-6 border border-border flex items-start justify-between">
                <div className="flex items-center gap-6">
                    <div className={cn(
                        "w-20 h-20 rounded-full flex items-center justify-center text-3xl text-primary-foreground font-bold shadow-lg",
                        isAIAssistant ? "bg-gradient-to-br from-purple-500 to-pink-500" : "bg-gradient-primary"
                    )}>
                        {isAIAssistant ? '🤖' : employee.name.slice(0, 1)}
                    </div>
                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <h1 className="text-2xl font-bold text-foreground">{employee.name}</h1>
                            <span className={cn("px-3 py-1 text-xs rounded-full font-medium", roleBadge.className)}>
                                {roleBadge.label}
                            </span>
                            {employee.employee_number && (
                                <span className="px-2 py-0.5 text-xs rounded bg-secondary text-muted-foreground font-mono">
                                    {employee.employee_number}
                                </span>
                            )}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                            <span className="flex items-center gap-1">
                                <Mail className="w-4 h-4" />
                                {employee.department || '无部门'}
                            </span>
                            {employee.job_title && (
                                <span className="flex items-center gap-1">
                                    {employee.job_title}
                                </span>
                            )}
                            <span className="flex items-center gap-1">
                                <Calendar className="w-4 h-4" />
                                入职日期: {new Date(employee.created_at).toLocaleDateString('zh-CN')}
                            </span>
                        </div>
                    </div>
                </div>

                <div className="flex gap-3">
                    {isBossUser && (
                        <Button variant="outline" onClick={() => {
                            setEditForm({
                                employee_number: employee.employee_number || '',
                                department: employee.department || '',
                                job_title: employee.job_title || '',
                                role: employee.role || '',
                            });
                            setShowEditDialog(true);
                        }}>
                            <Pencil className="w-4 h-4 mr-2" />
                            编辑信息
                        </Button>
                    )}
                    <Button variant="outline" onClick={() => setShowTransferDialog(true)}>
                        <ArrowRightLeft className="w-4 h-4 mr-2" />
                        数据移交
                    </Button>
                    <Button variant="destructive" onClick={() => setShowDeleteDialog(true)}>
                        <Trash2 className="w-4 h-4 mr-2" />
                        删除员工
                    </Button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-card p-5 rounded-xl border border-border">
                    <div className="flex items-center gap-3 mb-3">
                        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                            <BarChart3 className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                            <p className="text-sm text-muted-foreground">总积分</p>
                            <p className="text-2xl font-bold text-foreground">{employee.score}</p>
                        </div>
                    </div>
                    <p className="text-xs text-muted-foreground pl-13">团队排名 #{employee.rank}</p>
                </div>

                <div className="bg-card p-5 rounded-xl border border-border">
                    <div className="flex items-center gap-3 mb-3">
                        <div className="w-10 h-10 rounded-lg bg-gold/10 flex items-center justify-center">
                            <Award className="w-5 h-5 text-gold" />
                        </div>
                        <div>
                            <p className="text-sm text-muted-foreground">获得徽章</p>
                            <p className="text-2xl font-bold text-foreground">{stats?.badgesCount || 0}</p>
                        </div>
                    </div>
                    <p className="text-xs text-muted-foreground pl-13">累计获得荣誉</p>
                </div>

                <div className="bg-card p-5 rounded-xl border border-border">
                    <div className="flex items-center gap-3 mb-3">
                        <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center">
                            <FileCheck className="w-5 h-5 text-success" />
                        </div>
                        <div>
                            <p className="text-sm text-muted-foreground">总奖金</p>
                            <p className="text-2xl font-bold text-foreground">¥{employee.total_bonus}</p>
                        </div>
                    </div>
                    <p className="text-xs text-muted-foreground pl-13">累计发放激励</p>
                </div>
            </div>

            {/* Projects Section */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-foreground">负责项目</h3>
                    <Button variant="outline" size="sm" onClick={() => setShowTransferDialog(true)} disabled={selectedProjects.length === 0}>
                        <ArrowRightLeft className="w-4 h-4 mr-2" />
                        批量移交选定项目 ({selectedProjects.length})
                    </Button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {projects.map(project => (
                        <div
                            key={project.id}
                            className={cn(
                                "bg-card border rounded-xl p-5 hover:border-primary/50 transition-all cursor-pointer relative group",
                                selectedProjects.includes(project.id) ? "border-primary bg-primary/5" : "border-border"
                            )}
                            onClick={() => onProjectSelect?.(project.id)}
                        >
                            {/* Checkbox for selection */}
                            <div
                                className={cn(
                                    "absolute top-4 right-4 w-5 h-5 rounded border flex items-center justify-center transition-colors z-20",
                                    selectedProjects.includes(project.id)
                                        ? "bg-primary border-primary text-primary-foreground"
                                        : "border-muted-foreground/30 group-hover:border-primary/50"
                                )}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    toggleProjectSelection(project.id);
                                }}
                            >
                                {selectedProjects.includes(project.id) && <CheckCircle2 className="w-3.5 h-3.5" />}
                            </div>

                            <div className="mb-4">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className={cn(
                                        "px-2 py-0.5 text-[10px] rounded-full font-medium uppercase",
                                        project.type === 'SaaS' ? "bg-blue-500/10 text-blue-500" :
                                            project.type === '私有化' ? "bg-purple-500/10 text-purple-500" :
                                                "bg-orange-500/10 text-orange-500"
                                    )}>
                                        {project.type}
                                    </span>
                                    <span className="text-xs text-muted-foreground">{new Date(project.updated_at).toLocaleDateString()} 更新</span>
                                </div>
                                <h4 className="font-semibold text-foreground">{project.name}</h4>
                                <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{project.description}</p>
                            </div>

                            {/* Progress Bar */}
                            <div className="space-y-2">
                                <div className="flex justify-between text-xs">
                                    <span className="text-muted-foreground">{project.stage}</span>
                                    <span className="font-medium text-foreground">{project.progress}%</span>
                                </div>
                                <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                                    <div
                                        className={cn(
                                            "h-full rounded-full transition-all duration-500",
                                            project.progress >= 80 ? "bg-success" :
                                                project.progress >= 50 ? "bg-primary" : "bg-warning"
                                        )}
                                        style={{ width: `${project.progress}%` }}
                                    />
                                </div>
                            </div>
                        </div>
                    ))}

                    {/* Add New Project Placeholder */}
                    <div className="border border-dashed border-border rounded-xl p-5 flex flex-col items-center justify-center text-muted-foreground hover:bg-secondary/50 transition-colors cursor-not-allowed opacity-60">
                        <div className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center mb-2">
                            <Plus className="w-5 h-5" />
                        </div>
                        <p className="text-sm font-medium">新建项目</p>
                    </div>
                </div>
            </div>
            <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2 text-destructive">
                            <AlertTriangle className="w-5 h-5" />
                            确认删除员工
                        </DialogTitle>
                        <DialogDescription>
                            您即将删除员工 <strong>{employee.name}</strong>。此操作不可撤销。
                        </DialogDescription>
                    </DialogHeader>

                    <div className="bg-warning/10 border border-warning/30 rounded-lg p-4 text-sm text-warning my-4">
                        <p className="font-medium mb-1">警告</p>
                        <p>删除员工将导致其所有业绩数据、徽章和审批记录永久丢失。如需保留数据，请先进行数据转移。</p>
                    </div>

                    <div className="flex justify-end gap-3 pt-4">
                        <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
                            取消
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={() => onDelete(employee.user_id)}
                            disabled={isProcessing}
                        >
                            {isProcessing && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                            确认删除
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>

            {/* Transfer Dialog */}
            <Dialog open={showTransferDialog} onOpenChange={setShowTransferDialog}>
                <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <ArrowRightLeft className="w-5 h-5 text-primary" />
                            数据转移
                        </DialogTitle>
                        <DialogDescription>
                            将员工 <strong>{employee.name}</strong> 的数据转移给其他员工
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 mt-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-foreground">选择接收员工</label>
                            <Select value={transferTargetId} onValueChange={setTransferTargetId}>
                                <SelectTrigger>
                                    <SelectValue placeholder="选择员工..." />
                                </SelectTrigger>
                                <SelectContent>
                                    {otherEmployees.map((e) => (
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
                            onClick={() => onTransfer(employee.user_id, transferTargetId)}
                            disabled={!transferTargetId || isProcessing}
                        >
                            {isProcessing && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                            仅转移数据
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={() => onTransferAndDelete(employee.user_id, transferTargetId)}
                            disabled={!transferTargetId || isProcessing}
                        >
                            {isProcessing && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                            转移并删除
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>

            {/* Edit Employee Dialog */}
            <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Pencil className="w-5 h-5 text-primary" />
                            编辑员工信息
                        </DialogTitle>
                        <DialogDescription>
                            修改 <strong>{employee.name}</strong> 的角色、部门、工号和职务
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 mt-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-foreground">角色</label>
                            <Select
                                value={editForm.role}
                                onValueChange={(value) => setEditForm(prev => ({ ...prev, role: value }))}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="选择角色" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="employee">员工</SelectItem>
                                    <SelectItem value="manager">经理</SelectItem>
                                    <SelectItem value="boss">老板</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-foreground">部门</label>
                            <Select
                                value={editForm.department}
                                onValueChange={(value) => setEditForm(prev => ({ ...prev, department: value === '__none__' ? '' : value }))}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="选择部门" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="__none__">未分配</SelectItem>
                                    {departments?.map((dept) => (
                                        <SelectItem key={dept.id} value={dept.name}>
                                            {dept.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-foreground">工号</label>
                            <Input
                                placeholder="请输入工号，如 EMP001"
                                value={editForm.employee_number}
                                onChange={(e) => setEditForm(prev => ({ ...prev, employee_number: e.target.value }))}
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-foreground">职务</label>
                            <Input
                                placeholder="请输入职务，如 高级工程师"
                                value={editForm.job_title}
                                onChange={(e) => setEditForm(prev => ({ ...prev, job_title: e.target.value }))}
                            />
                        </div>
                    </div>

                    <div className="flex justify-end gap-3 pt-4">
                        <Button variant="outline" onClick={() => setShowEditDialog(false)}>
                            取消
                        </Button>
                        <Button
                            onClick={handleEditSave}
                            disabled={updateEmployee.isPending}
                        >
                            {updateEmployee.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                            保存
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
