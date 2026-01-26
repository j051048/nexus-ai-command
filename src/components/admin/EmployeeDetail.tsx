import React from 'react';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Mail, Phone, Calendar, Award, BarChart3, FileCheck, Trash2, ArrowRightLeft } from 'lucide-react';
import { Employee, useEmployeeStats } from '@/hooks/useEmployeeManagement';
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

interface EmployeeDetailProps {
    employee: Employee;
    allEmployees: Employee[];
    onBack: () => void;
    onDelete: (id: string) => void;
    onTransfer: (fromId: string, toId: string) => void;
    onTransferAndDelete: (fromId: string, toId: string) => void;
    isProcessing: boolean;
}

export function EmployeeDetail({
    employee,
    allEmployees,
    onBack,
    onDelete,
    onTransfer,
    onTransferAndDelete,
    isProcessing
}: EmployeeDetailProps) {
    const { data: stats } = useEmployeeStats(employee.user_id);
    const [showDeleteDialog, setShowDeleteDialog] = React.useState(false);
    const [showTransferDialog, setShowTransferDialog] = React.useState(false);
    const [transferTargetId, setTransferTargetId] = React.useState<string>('');

    const otherEmployees = allEmployees.filter(e => e.user_id !== employee.user_id);
    const isBoss = employee.role === 'boss';

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
                    <div className="w-20 h-20 rounded-full bg-gradient-primary flex items-center justify-center text-3xl text-primary-foreground font-bold shadow-lg">
                        {employee.name.slice(0, 1)}
                    </div>
                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <h1 className="text-2xl font-bold text-foreground">{employee.name}</h1>
                            <span className={cn(
                                "px-3 py-1 text-xs rounded-full font-medium",
                                isBoss ? "bg-gold/20 text-gold" : "bg-primary/20 text-primary"
                            )}>
                                {isBoss ? '老板' : '员工'}
                            </span>
                        </div>
                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                            <span className="flex items-center gap-1">
                                <Mail className="w-4 h-4" />
                                {employee.department || '无部门'}
                            </span>
                            <span className="flex items-center gap-1">
                                <Calendar className="w-4 h-4" />
                                入职日期: {new Date(employee.created_at).toLocaleDateString('zh-CN')}
                            </span>
                        </div>
                    </div>
                </div>

                <div className="flex gap-3">
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

            {/* Delete Dialog */}
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
                <DialogContent className="max-w-lg">
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
        </div>
    );
}
