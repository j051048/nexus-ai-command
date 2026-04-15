import React from 'react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
    Clock,
    CheckCircle2,
    XCircle,
    Undo2,
    RefreshCw,
    User,
    Calendar,
    DollarSign,
    FileText,
    MessageSquare,
    Bot,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ApprovalProgressTracker } from './ApprovalProgressTracker';
import { useApprovalProgress } from '@/hooks/useApprovals';

// ─── Types ────────────────────────────────────────────────

interface ApprovalItem {
    id: string;
    type: string;
    description: string;
    amount: number;
    status: string;
    created_at: string;
    submitter_name?: string;
    submitted_by?: string;
    submitted_via?: string;
    approved_by?: string;
    approved_at?: string;
    approval_comment?: string;
    ai_decision?: string;
    ai_reason?: string;
    form_data?: Record<string, unknown>;
    resubmit_count?: number;
    approval_history?: Array<{
        step: number;
        decision: string;
        approver_name?: string;
        comment?: string;
        timestamp?: string;
    }>;
    [key: string]: unknown;
}

interface ApprovalDetailDialogProps {
    item: ApprovalItem | null;
    open: boolean;
    onClose: () => void;
    /** 是否显示操作按钮（审批人视角） */
    showActions?: boolean;
    onApprove?: (id: string) => void;
    onReject?: (id: string) => void;
}

// ─── Status config ────────────────────────────────────────

const statusMap: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
    pending: { label: '待处理', color: 'bg-warning/20 text-warning', icon: <Clock className="w-4 h-4" /> },
    approved: { label: '已批准', color: 'bg-success/20 text-success', icon: <CheckCircle2 className="w-4 h-4" /> },
    rejected: { label: '已驳回', color: 'bg-destructive/20 text-destructive', icon: <XCircle className="w-4 h-4" /> },
    pending_resubmit: { label: '待重提', color: 'bg-orange-500/20 text-orange-600', icon: <RefreshCw className="w-4 h-4" /> },
    recalled: { label: '已撤回', color: 'bg-muted text-muted-foreground', icon: <Undo2 className="w-4 h-4" /> },
};

const typeLabels: Record<string, string> = {
    travel: '出差申请',
    purchase: '采购申请',
    expense: '费用报销',
    leave: '请假申请',
    business_trip: '商务出行',
    general: '通用审批',
};

// ─── Progress wrapper ──────────────────────────────────────

function DetailProgress({ requestId }: { requestId: string }) {
    const { data: progressData, isLoading } = useApprovalProgress(requestId);

    if (isLoading) {
        return <p className="text-sm text-muted-foreground py-4 text-center">加载审批链...</p>;
    }

    if (!progressData?.steps?.length) {
        return <p className="text-sm text-muted-foreground py-2">暂无审批链信息</p>;
    }

    return (
        <ApprovalProgressTracker
            steps={progressData.steps}
            currentStep={progressData.current_step}
            approvalHistory={progressData.approval_history}
            status={progressData.status}
        />
    );
}

// ─── Main component ────────────────────────────────────────

export function ApprovalDetailDialog({
    item,
    open,
    onClose,
    showActions = false,
    onApprove,
    onReject,
}: ApprovalDetailDialogProps) {
    if (!item) return null;

    const status = statusMap[item.status] || statusMap.pending;
    const historyEntries = item.approval_history || [];

    return (
        <Dialog open={open} onOpenChange={onClose}>
            <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                    <div className="flex items-center justify-between">
                        <DialogTitle className="text-lg">审批详情</DialogTitle>
                        <div className={cn("flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold", status.color)}>
                            {status.icon}
                            {status.label}
                        </div>
                    </div>
                </DialogHeader>

                <div className="space-y-5 pt-2">
                    {/* ─── 基本信息 ─── */}
                    <section className="space-y-3">
                        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                            <FileText className="w-4 h-4 text-muted-foreground" />
                            申请信息
                        </h3>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                            <InfoRow label="审批类型" value={typeLabels[item.type] || item.type} />
                            <InfoRow label="申请人" value={item.submitter_name || '—'} icon={<User className="w-3.5 h-3.5" />} />
                            {item.amount > 0 && (
                                <InfoRow label="金额" value={`¥${item.amount.toLocaleString()}`} icon={<DollarSign className="w-3.5 h-3.5" />} />
                            )}
                            <InfoRow
                                label="提交时间"
                                value={new Date(item.created_at).toLocaleString('zh-CN')}
                                icon={<Calendar className="w-3.5 h-3.5" />}
                            />
                        </div>

                        {item.description && (
                            <div className="bg-secondary/30 rounded-lg p-3">
                                <p className="text-sm text-foreground whitespace-pre-wrap">{item.description}</p>
                            </div>
                        )}

                        {item.submitted_via === 'ai_assistant' && (
                            <Badge variant="secondary" className="gap-1 text-purple-600">
                                <Bot className="w-3 h-3" /> AI 代提交
                            </Badge>
                        )}

                        {(item.resubmit_count ?? 0) > 0 && (
                            <Badge variant="outline" className="gap-1">
                                <RefreshCw className="w-3 h-3" /> 第 {item.resubmit_count} 次重提
                            </Badge>
                        )}
                    </section>

                    {/* ─── 表单数据 ─── */}
                    {item.form_data && Object.keys(item.form_data).length > 0 && (
                        <>
                            <Separator />
                            <section className="space-y-3">
                                <h3 className="text-sm font-semibold text-foreground">表单数据</h3>
                                <div className="bg-secondary/30 rounded-lg p-3 space-y-2">
                                    {Object.entries(item.form_data).map(([key, value]) => (
                                        <div key={key} className="flex justify-between text-sm">
                                            <span className="text-muted-foreground">{key}</span>
                                            <span className="text-foreground font-medium">{String(value)}</span>
                                        </div>
                                    ))}
                                </div>
                            </section>
                        </>
                    )}

                    {/* ─── 审批链进度 ─── */}
                    <Separator />
                    <section className="space-y-3">
                        <h3 className="text-sm font-semibold text-foreground">审批流程</h3>
                        <DetailProgress requestId={item.id} />
                    </section>

                    {/* ─── 审批意见历史 ─── */}
                    {historyEntries.length > 0 && (
                        <>
                            <Separator />
                            <section className="space-y-3">
                                <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                                    <MessageSquare className="w-4 h-4 text-muted-foreground" />
                                    审批意见
                                </h3>
                                <div className="space-y-2">
                                    {historyEntries.map((entry, idx) => (
                                        <div key={idx} className="flex gap-3 text-sm bg-secondary/20 rounded-lg p-3">
                                            <div className={cn(
                                                "w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5",
                                                entry.decision === 'approved' ? 'bg-success/20 text-success' : 'bg-destructive/20 text-destructive'
                                            )}>
                                                {entry.decision === 'approved' ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-medium">{entry.approver_name || '审批人'}</span>
                                                    <span className="text-xs text-muted-foreground">
                                                        {entry.decision === 'approved' ? '批准' : '驳回'}
                                                    </span>
                                                    {entry.timestamp && (
                                                        <span className="text-xs text-muted-foreground ml-auto">
                                                            {new Date(entry.timestamp).toLocaleString('zh-CN')}
                                                        </span>
                                                    )}
                                                </div>
                                                {entry.comment && (
                                                    <p className="text-muted-foreground mt-1 whitespace-pre-wrap">{entry.comment}</p>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </section>
                        </>
                    )}

                    {/* ─── AI 分析 ─── */}
                    {item.ai_reason && (
                        <>
                            <Separator />
                            <section className="space-y-2">
                                <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                                    <Bot className="w-4 h-4 text-purple-500" />
                                    AI 分析
                                </h3>
                                <div className="bg-purple-50 dark:bg-purple-950/20 rounded-lg p-3">
                                    <p className="text-sm text-foreground">{item.ai_reason}</p>
                                </div>
                            </section>
                        </>
                    )}

                    {/* ─── 操作按钮（审批人视角） ─── */}
                    {showActions && item.status === 'pending' && (
                        <>
                            <Separator />
                            <div className="flex justify-end gap-3 pt-1">
                                <Button
                                    variant="destructive"
                                    onClick={() => onReject?.(item.id)}
                                >
                                    驳回
                                </Button>
                                <Button
                                    className="bg-emerald-600 hover:bg-emerald-700"
                                    onClick={() => onApprove?.(item.id)}
                                >
                                    批准
                                </Button>
                            </div>
                        </>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}

// ─── Helper ────────────────────────────────────────────────

function InfoRow({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
    return (
        <div className="flex flex-col gap-0.5">
            <span className="text-xs text-muted-foreground">{label}</span>
            <span className="text-sm font-medium text-foreground flex items-center gap-1.5">
                {icon}
                {value}
            </span>
        </div>
    );
}
