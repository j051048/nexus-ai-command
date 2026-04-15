import React, { useState, useEffect } from 'react';
import { useIsMobile } from '@/hooks/use-mobile';
import {
    CheckCircle2,
    AlertTriangle,
    Sparkles,
    Loader2,
    XCircle,
    CheckSquare,
    X,
    GitBranch,
    Eye,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import {
    useAllApprovals,
    usePendingApprovalsCount,
    useApproveRequest,
    useRejectRequest,
    useAdvanceApproval,
    useApprovalProgress,
} from '@/hooks/useApprovals';
import { BossApprovalCard } from '../components/BossApprovalCard';
import { ApprovalDetailDialog } from '../components/ApprovalDetailDialog';
import { approvalTypes } from '../constants';
import { useFormSchema } from '@/hooks/useFormSchemas';
import { DynamicFormRenderer } from '@/components/forms/DynamicFormRenderer';
import { useAuth } from '@/components/auth/AuthContext';
import type { ApprovalRequest } from '@/hooks/useApprovals';

// ─── 小型内联审批进度指示器 ──────────────────────────────────
// 在审批列表项中显示简化的审批链进度
function MiniApprovalProgress({ requestId }: { requestId: string }) {
    const { data: progressData } = useApprovalProgress(requestId);

    if (!progressData || !progressData.steps || progressData.steps.length === 0) {
        return null;
    }

    const { steps, current_step, status } = progressData;
    const totalSteps = steps.length;
    const completedSteps = current_step;
    const progressPct = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;

    return (
        <div className="flex items-center gap-2 mt-2">
            <GitBranch className="w-3 h-3 text-muted-foreground flex-shrink-0" />
            <div className="flex-1 flex items-center gap-1.5">
                <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                        className={cn(
                            'h-full rounded-full transition-all',
                            status === 'rejected' ? 'bg-destructive' :
                            status === 'approved' ? 'bg-success' :
                            'bg-primary'
                        )}
                        style={{ width: `${status === 'approved' ? 100 : progressPct}%` }}
                    />
                </div>
                <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                    {completedSteps}/{totalSteps}
                </span>
            </div>
        </div>
    );
}

export function BossApprovalView() {
    const { user } = useAuth();
    const [statusFilter, setStatusFilter] = useState('pending');
    const [rejectingId, setRejectingId] = useState<string | null>(null);
    const [rejectReason, setRejectReason] = useState('');
    const [approvingId, setApprovingId] = useState<string | null>(null);
    const [approveComment, setApproveComment] = useState('');
    const isMobile = useIsMobile();
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [isBatchProcessing, setIsBatchProcessing] = useState(false);
    const [detailItem, setDetailItem] = useState<ApprovalRequest | null>(null);

    const { data: allApprovals, isLoading } = useAllApprovals(statusFilter);
    const { data: pendingCount } = usePendingApprovalsCount();
    const approveRequest = useApproveRequest();
    const rejectRequest = useRejectRequest();
    const advanceApproval = useAdvanceApproval();


    // 当筛选条件变化时清空选择
    useEffect(() => {
        setSelectedIds(new Set());
    }, [statusFilter]);

    // 待处理项目列表（用于批量操作）
    const pendingApprovals = allApprovals?.filter(a => a.status === 'pending') || [];

    // 全选/取消全选
    const handleSelectAll = (checked: boolean) => {
        if (checked) {
            const allPendingIds = new Set(pendingApprovals.map(a => a.id));
            setSelectedIds(allPendingIds);
        } else {
            setSelectedIds(new Set());
        }
    };

    // 单选切换
    const handleToggleSelect = (id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    };

    // 取消选择
    const handleClearSelection = () => {
        setSelectedIds(new Set());
    };

    // 是否全选
    const isAllSelected = pendingApprovals.length > 0 && pendingApprovals.every(a => selectedIds.has(a.id));
    const isSomeSelected = selectedIds.size > 0;

    const handleApprove = (requestId: string) => {
        setApprovingId(requestId);
        setApproveComment('');
    };

    const handleConfirmApprove = async () => {
        if (!approvingId) return;
        try {
            await advanceApproval.mutateAsync({
                requestId: approvingId,
                decision: 'approved',
                comment: approveComment.trim() || undefined,
            });
            toast.success('已批准该项申请');
            setApprovingId(null);
            setApproveComment('');
        } catch {
            try {
                await approveRequest.mutateAsync(approvingId);
                toast.success('已批准该项申请');
                setApprovingId(null);
                setApproveComment('');
            } catch (error: unknown) {
                const err = error as Error;
                toast.error('操作失败: ' + err.message);
            }
        }
    };

    const handleReject = async () => {
        if (!rejectingId || !rejectReason.trim()) {
            toast.error('请填写驳回原因');
            return;
        }

        try {
            // Try advance endpoint first (supports multi-step chains)
            await advanceApproval.mutateAsync({
                requestId: rejectingId,
                decision: 'rejected',
                comment: rejectReason,
            });
            toast.success('申请被驳回');
            setRejectingId(null);
            setRejectReason('');
        } catch {
            // Fallback to direct reject if advance endpoint not available
            try {
                await rejectRequest.mutateAsync({ requestId: rejectingId, reason: rejectReason });
                toast.success('申请被驳回');
                setRejectingId(null);
                setRejectReason('');
            } catch (error: unknown) {
                const err = error as Error;
                toast.error('操作失败: ' + err.message);
            }
        }
    };

    // 批量通过
    const handleBatchApprove = async () => {
        if (selectedIds.size === 0) return;
        setIsBatchProcessing(true);
        let successCount = 0;
        let failCount = 0;

        for (const id of selectedIds) {
            try {
                await advanceApproval.mutateAsync({ requestId: id, decision: 'approved' });
                successCount++;
            } catch {
                // Fallback to direct approve
                try {
                    await approveRequest.mutateAsync(id);
                    successCount++;
                } catch {
                    failCount++;
                }
            }
        }

        setIsBatchProcessing(false);
        setSelectedIds(new Set());

        if (failCount === 0) {
            toast.success(`已批量通过 ${successCount} 项申请`);
        } else {
            toast.warning(`批量操作完成：${successCount} 项通过，${failCount} 项失败`);
        }
    };

    // 批量驳回
    const handleBatchReject = async () => {
        if (selectedIds.size === 0) return;
        setIsBatchProcessing(true);
        let successCount = 0;
        let failCount = 0;

        for (const id of selectedIds) {
            try {
                await advanceApproval.mutateAsync({ requestId: id, decision: 'rejected', comment: '批量驳回' });
                successCount++;
            } catch {
                // Fallback to direct reject
                try {
                    await rejectRequest.mutateAsync({ requestId: id, reason: '批量驳回' });
                    successCount++;
                } catch {
                    failCount++;
                }
            }
        }

        setIsBatchProcessing(false);
        setSelectedIds(new Set());

        if (failCount === 0) {
            toast.success(`已批量驳回 ${successCount} 项申请`);
        } else {
            toast.warning(`批量操作完成：${successCount} 项驳回，${failCount} 项失败`);
        }
    };

    return (
        <div className="space-y-6">
            {/* Boss Insight Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-card rounded-2xl p-5 border border-border shadow-sm">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">待人工审批</p>
                            <p className="text-3xl font-bold text-foreground mt-1">{pendingCount || 0}</p>
                        </div>
                        <div className="w-12 h-12 rounded-xl bg-warning/10 flex items-center justify-center">
                            <AlertTriangle className="w-6 h-6 text-warning" />
                        </div>
                    </div>
                </div>
                <div className="bg-card rounded-2xl p-5 border border-border shadow-sm">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">今日处理总量</p>
                            <p className="text-3xl font-bold text-foreground mt-1">
                                {allApprovals?.filter(a =>
                                    new Date(a.created_at).toDateString() === new Date().toDateString()
                                ).length || 0}
                            </p>
                        </div>
                        <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                            <CheckCircle2 className="w-6 h-6 text-primary" />
                        </div>
                    </div>
                </div>
                <div className="bg-card rounded-2xl p-5 border border-border shadow-sm relative overflow-hidden group">
                    <div className="absolute inset-0 bg-gradient-to-br from-success/5 to-transparent pointer-events-none" />
                    <div className="flex items-center justify-between relative">
                        <div>
                            <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">AI 自动化节约时间</p>
                            <p className="text-3xl font-bold text-success mt-1">~12.4h</p>
                        </div>
                        <div className="w-12 h-12 rounded-xl bg-success/10 flex items-center justify-center text-success group-hover:scale-110 transition-transform">
                            <Sparkles className="w-6 h-6" />
                        </div>
                    </div>
                </div>
            </div>

            <Tabs value={statusFilter} onValueChange={setStatusFilter} className="w-full">
                <div className="flex items-center justify-between mb-4">
                    <TabsList className="bg-background/50 border border-border">
                        <TabsTrigger value="pending" className="relative px-6">
                            待处理
                            {(pendingCount || 0) > 0 && (
                                <span className="absolute -top-1 -right-1 flex h-4 w-4">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-warning opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-4 w-4 bg-warning text-[10px] text-white font-bold items-center justify-center">{pendingCount}</span>
                                </span>
                            )}
                        </TabsTrigger>
                        <TabsTrigger value="approved" className="px-6">已批准</TabsTrigger>
                        <TabsTrigger value="rejected" className="px-6">已驳回</TabsTrigger>
                        <TabsTrigger value="all" className="px-6">全纪录</TabsTrigger>
                    </TabsList>

                    {/* 全选 checkbox — 仅在待处理 tab 且有数据时显示 */}
                    {statusFilter === 'pending' && pendingApprovals.length > 0 && (
                        <div className="flex items-center gap-2">
                            <Checkbox
                                id="select-all-approvals"
                                checked={isAllSelected}
                                onCheckedChange={(checked) => handleSelectAll(!!checked)}
                            />
                            <label
                                htmlFor="select-all-approvals"
                                className="text-sm font-medium text-muted-foreground cursor-pointer select-none"
                            >
                                全选
                            </label>
                        </div>
                    )}
                </div>

                <TabsContent value={statusFilter} className="mt-0 focus-visible:outline-none focus-visible:ring-0">
                    <div className="bg-card rounded-2xl p-6 border border-border shadow-sm min-h-[400px]">
                        {isLoading ? (
                            <div className="flex flex-col items-center justify-center py-20 gap-4">
                                <Loader2 className="w-10 h-10 animate-spin text-primary" />
                                <p className="text-sm text-muted-foreground">正在同步同步大模型决策...</p>
                            </div>
                        ) : !allApprovals || allApprovals.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                                <div className="w-20 h-20 rounded-full bg-secondary flex items-center justify-center mb-4">
                                    <CheckCircle2 className="w-10 h-10 opacity-20" />
                                </div>
                                <h3 className="text-lg font-medium text-foreground">全部处理完毕</h3>
                                <p className="text-sm mt-1">目前没有需要您关注的异常申请</p>
                            </div>
                        ) : (
                            // A6: 移动端卡片视图，桌面端列表视图
                            <div className={cn(
                                isMobile ? "space-y-4" : "grid grid-cols-1 gap-4"
                            )}>
                                {allApprovals.map((approval) => (
                                    isMobile ? (
                                        // A6: 移动端卡片
                                        <div
                                            key={approval.id}
                                            className="bg-card rounded-xl border border-border p-4 space-y-3 shadow-sm"
                                        >
                                            <div className="flex items-start gap-3">
                                                {/* 批量选择 checkbox */}
                                                {approval.status === 'pending' && (
                                                    <Checkbox
                                                        checked={selectedIds.has(approval.id)}
                                                        onCheckedChange={() => handleToggleSelect(approval.id)}
                                                        className="mt-1 flex-shrink-0"
                                                    />
                                                )}
                                                <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center text-muted-foreground flex-shrink-0">
                                                    {approvalTypes.find(t => t.id === approval.type)?.icon}
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <p className="font-medium text-foreground text-sm">{approval.description}</p>
                                                    <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                                                        <span>{approval.submitter_name}</span>
                                                        <span>•</span>
                                                        <span className="font-medium text-foreground">¥{approval.amount}</span>
                                                    </div>
                                                </div>
                                            </div>
                                            
                                            {approval.ai_reason && (
                                                <div className="p-2 rounded bg-primary/5 border border-primary/10">
                                                    <p className="text-xs text-muted-foreground flex items-start gap-1">
                                                        <CheckCircle2 className="w-3 h-3 text-primary mt-0.5 flex-shrink-0" />
                                                        <span><span className="font-semibold text-primary">AI:</span> {approval.ai_reason}</span>
                                                    </p>
                                                </div>
                                            )}

                                            {/* 内联审批进度指示器 */}
                                            <MiniApprovalProgress requestId={approval.id} />

                                            {/* A6: 移动端批准/驳回按钮 */}
                                            {approval.status === 'pending' && approval.submitted_by !== user?.id ? (
                                                <div className="flex gap-2 pt-2">
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => setDetailItem(approval)}
                                                        className="text-muted-foreground"
                                                    >
                                                        <Eye className="w-4 h-4 mr-1" />
                                                        详情
                                                    </Button>
                                                    <div className="flex-1" />
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => setRejectingId(approval.id)}
                                                        className="text-destructive hover:text-destructive"
                                                    >
                                                        <XCircle className="w-4 h-4 mr-1" />
                                                        驳回
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        onClick={() => handleApprove(approval.id)}
                                                        disabled={approveRequest.isPending}
                                                        className="bg-success hover:bg-success/90"
                                                    >
                                                        {approveRequest.isPending ? (
                                                            <Loader2 className="w-4 h-4 animate-spin" />
                                                        ) : (
                                                            <>
                                                                <CheckCircle2 className="w-4 h-4 mr-1" />
                                                                批准
                                                            </>
                                                        )}
                                                    </Button>
                                                </div>
                                            ) : (
                                                <div className="flex gap-2 pt-2">
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => setDetailItem(approval)}
                                                        className="text-muted-foreground"
                                                    >
                                                        <Eye className="w-4 h-4 mr-1" />
                                                        详情
                                                    </Button>
                                                </div>
                                            )}
                                        </div>
                                    ) : (
                                        // A6: 桌面端保持原有组件，增加 checkbox
                                        <div key={approval.id} className="flex items-start gap-3">
                                            {approval.status === 'pending' && (
                                                <Checkbox
                                                    checked={selectedIds.has(approval.id)}
                                                    onCheckedChange={() => handleToggleSelect(approval.id)}
                                                    className="mt-5 flex-shrink-0"
                                                />
                                            )}
                                            <div className="flex-1">
                                                <BossApprovalCard
                                                    approval={approval}
                                                    onApprove={() => handleApprove(approval.id)}
                                                    onReject={() => setRejectingId(approval.id)}
                                                    onViewDetail={() => setDetailItem(approval)}
                                                    isApproving={approveRequest.isPending}
                                                    typeIcon={approvalTypes.find(t => t.id === approval.type)?.icon}
                                                    currentUserId={user?.id}
                                                />
                                            </div>
                                        </div>
                                    )
                                ))}
                            </div>
                        )}
                    </div>
                </TabsContent>
            </Tabs>

            {/* Floating Batch Action Bar */}
            {isSomeSelected && (
                <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-6 py-3 rounded-2xl bg-card border border-border shadow-2xl backdrop-blur-sm">
                    <CheckSquare className="w-5 h-5 text-primary" />
                    <span className="text-sm font-medium text-foreground whitespace-nowrap">
                        已选择 <span className="text-primary font-bold">{selectedIds.size}</span> 项
                    </span>
                    <div className="w-px h-6 bg-border mx-1" />
                    <Button
                        size="sm"
                        onClick={handleBatchApprove}
                        disabled={isBatchProcessing}
                        className="bg-success hover:bg-success/90 gap-1"
                    >
                        {isBatchProcessing ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <CheckCircle2 className="w-4 h-4" />
                        )}
                        批量通过
                    </Button>
                    <Button
                        size="sm"
                        variant="destructive"
                        onClick={handleBatchReject}
                        disabled={isBatchProcessing}
                        className="gap-1"
                    >
                        {isBatchProcessing ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <XCircle className="w-4 h-4" />
                        )}
                        批量驳回
                    </Button>
                    <Button
                        size="sm"
                        variant="ghost"
                        onClick={handleClearSelection}
                        disabled={isBatchProcessing}
                        className="gap-1 text-muted-foreground"
                    >
                        <X className="w-4 h-4" />
                        取消选择
                    </Button>
                </div>
            )}

            {/* Reject Reason Dialog */}
            <Dialog open={!!rejectingId} onOpenChange={() => setRejectingId(null)}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>填写驳回建议</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 pt-4">
                        <Textarea
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            placeholder="请输入驳回理由，员工将实时收到通知..."
                            className="min-h-32 resize-none"
                        />
                        <div className="flex justify-end gap-3">
                            <Button variant="outline" onClick={() => setRejectingId(null)}>返回</Button>
                            <Button
                                variant="destructive"
                                onClick={handleReject}
                                disabled={rejectRequest.isPending}
                                className="px-8 shadow-lg shadow-destructive/20"
                            >
                                {rejectRequest.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "确认驳回"}
                            </Button>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>

            {/* 批准确认弹窗 */}
            <Dialog open={!!approvingId} onOpenChange={() => setApprovingId(null)}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>确认批准</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 pt-4">
                        <Textarea
                            value={approveComment}
                            onChange={(e) => setApproveComment(e.target.value)}
                            placeholder="填写审批意见（可选）"
                            className="min-h-24 resize-none"
                        />
                        <div className="flex justify-end gap-3">
                            <Button variant="outline" onClick={() => setApprovingId(null)}>返回</Button>
                            <Button
                                onClick={handleConfirmApprove}
                                disabled={advanceApproval.isPending}
                                className="px-8 bg-emerald-600 hover:bg-emerald-700 shadow-lg shadow-emerald-600/20"
                            >
                                {advanceApproval.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "确认批准"}
                            </Button>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>

            {/* 审批详情弹窗 */}
            <ApprovalDetailDialog
                item={detailItem as Parameters<typeof ApprovalDetailDialog>[0]['item']}
                open={!!detailItem}
                onClose={() => setDetailItem(null)}
                showActions={detailItem?.status === 'pending' && detailItem?.submitted_by !== user?.id}
                onApprove={(id) => { setDetailItem(null); handleApprove(id); }}
                onReject={(id) => { setDetailItem(null); setRejectingId(id); }}
            />
        </div>
    );
}
