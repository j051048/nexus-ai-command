import React, { useState } from 'react';
import { Clock, Loader2, CheckCircle2, XCircle, Bot, ChevronDown, ChevronUp, BellRing, Plane, ShoppingCart, Receipt, Calendar as CalendarIcon, Undo2, RefreshCw, Eye } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ApprovalRequest, useApprovalProgress, useUrgeApproval, useRecallApproval, useResubmitApproval } from '@/hooks/useApprovals';
import { AICopilotInsight } from '@/components/common/AICopilotInsight';
import { ApprovalProgressTracker } from '../components/ApprovalProgressTracker';
import { ApprovalDetailDialog } from '../components/ApprovalDetailDialog';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
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

const approvalTypes = [
    { id: 'travel', icon: <Plane className="w-4 h-4" /> },
    { id: 'purchase', icon: <ShoppingCart className="w-4 h-4" /> },
    { id: 'expense', icon: <Receipt className="w-4 h-4" /> },
    { id: 'leave', icon: <CalendarIcon className="w-4 h-4" /> },
];

const statusConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
    pending: { label: '待处理', color: 'bg-warning/20 text-warning', icon: <Clock className="w-3.5 h-3.5" /> },
    approved: { label: '已批准', color: 'bg-success/20 text-success', icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
    rejected: { label: '已驳回', color: 'bg-destructive/20 text-destructive', icon: <XCircle className="w-3.5 h-3.5" /> },
    pending_resubmit: { label: '待重提', color: 'bg-orange-500/20 text-orange-600', icon: <RefreshCw className="w-3.5 h-3.5" /> },
    recalled: { label: '已撤回', color: 'bg-muted text-muted-foreground', icon: <Undo2 className="w-3.5 h-3.5" /> },
};

// ---- Inline progress display for a single history item ----

function HistoryItemProgress({ requestId }: { requestId: string }) {
    const { data: progressData, isLoading } = useApprovalProgress(requestId);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-3">
                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (!progressData || !progressData.steps || progressData.steps.length === 0) {
        return (
            <div className="py-2 px-3">
                <p className="text-xs text-muted-foreground">暂无审批链信息</p>
            </div>
        );
    }

    return (
        <div className="py-2 px-1">
            <ApprovalProgressTracker
                steps={progressData.steps}
                currentStep={progressData.current_step}
                approvalHistory={progressData.approval_history}
                status={progressData.status}
            />
        </div>
    );
}

interface ApprovalHistoryProps {
    approvals?: ApprovalRequest[];
    isLoading: boolean;
}

export function ApprovalHistory({
    approvals,
    isLoading
}: ApprovalHistoryProps) {
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const urgeMutation = useUrgeApproval();
    const recallMutation = useRecallApproval();
    const resubmitMutation = useResubmitApproval();
    const [recallingId, setRecallingId] = useState<string | null>(null);
    const [resubmittingItem, setResubmittingItem] = useState<ApprovalRequest | null>(null);
    const [resubmitDesc, setResubmitDesc] = useState('');
    const [resubmitAmount, setResubmitAmount] = useState('');
    const [detailItem, setDetailItem] = useState<ApprovalRequest | null>(null);
    const toggleExpand = (id: string) => {
        setExpandedId((prev) => (prev === id ? null : id));
    };

    const handleRecallConfirm = () => {
        if (!recallingId) return;
        recallMutation.mutate(recallingId, {
            onSuccess: () => setRecallingId(null),
        });
    };

    const openResubmit = (item: ApprovalRequest) => {
        setResubmittingItem(item);
        setResubmitDesc(item.description || '');
        setResubmitAmount(item.amount > 0 ? String(item.amount) : '');
    };

    const handleResubmit = () => {
        if (!resubmittingItem) return;
        resubmitMutation.mutate(
            {
                requestId: resubmittingItem.id,
                description: resubmitDesc.trim() || undefined,
                amount: resubmitAmount ? Number(resubmitAmount) : undefined,
            },
            { onSuccess: () => setResubmittingItem(null) }
        );
    };

    if (isLoading) {
        return (
            <div className="bg-card rounded-2xl p-6 border border-border">
                <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
            </div>
        );
    }

    return (
        <div className="bg-card rounded-2xl p-6 border border-border shadow-sm">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold text-foreground">我的历史申请</h2>
            </div>

            {!approvals || approvals.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                    <Clock className="w-12 h-12 mx-auto mb-3 opacity-20" />
                    <p>暂无审批记录</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {approvals.map((item) => {
                        const status = statusConfig[item.status] || statusConfig.pending;
                        const typeInfo = approvalTypes.find(t => t.id === item.type);
                        const isExpanded = expandedId === item.id;
                        const isPending = item.status === 'pending';
                        const canResubmit = item.status === 'rejected' || item.status === 'pending_resubmit';
                        const isUrging = urgeMutation.isPending && (urgeMutation.variables as string || null) === item.id;

                        return (
                            <div key={item.id} className="rounded-xl overflow-hidden">
                                <div
                                    className="flex items-center gap-4 p-4 bg-secondary/30 hover:bg-secondary/50 border border-transparent hover:border-border transition-all group cursor-pointer rounded-xl"
                                    onClick={() => toggleExpand(item.id)}
                                >
                                    <div className="w-10 h-10 rounded-lg bg-background flex items-center justify-center text-muted-foreground shadow-sm group-hover:scale-105 transition-transform">
                                        {typeInfo?.icon}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <p className="font-medium text-foreground truncate text-sm">{item.description}</p>
                                            <AICopilotInsight
                                                title={item.description}
                                                context={`Amount: ${item.amount}, Type: ${item.type}`}
                                                insights={[
                                                    { type: 'summary', content: '系统识别到该项支出属于常规差旅范畴。' },
                                                    { type: 'suggestion', content: '下次建议提前 3 天申请以获得更优的 AI 自动通过率。' }
                                                ]}
                                                className="opacity-0 group-hover:opacity-100"
                                            />
                                        </div>
                                        <div className="flex items-center gap-2 mt-0.5">
                                            <p className="text-xs text-muted-foreground">
                                                {new Date(item.created_at).toLocaleString('zh-CN')}
                                            </p>
                                            {(item as unknown as { submitted_via?: string }).submitted_via === 'ai_assistant' && (
                                                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-purple-500/10 text-purple-500">
                                                    <Bot className="w-3 h-3" />
                                                    豆豆代提交
                                                </span>
                                            )}
                                        </div>
                                    </div>

                                    {/* Action Area */}
                                    <div className="flex items-center gap-3 pr-2" onClick={e => e.stopPropagation()}>
                                        {item.amount > 0 && (
                                            <p className="text-sm font-bold text-foreground font-mono">¥{item.amount.toLocaleString()}</p>
                                        )}

                                        <TooltipProvider>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Button
                                                        size="icon"
                                                        variant="ghost"
                                                        onClick={() => setDetailItem(item)}
                                                        className="h-8 w-8 rounded-full hover:bg-primary/10 hover:text-primary"
                                                    >
                                                        <Eye className="h-4 w-4" />
                                                    </Button>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    <p>查看审批详情</p>
                                                </TooltipContent>
                                            </Tooltip>
                                        </TooltipProvider>

                                        {isPending && (
                                            <>
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button
                                                            size="icon"
                                                            variant="ghost"
                                                            disabled={isUrging}
                                                            onClick={() => urgeMutation.mutate(item.id)}
                                                            className="h-8 w-8 rounded-full hover:bg-warning/10 hover:text-warning group/urge overflow-hidden relative"
                                                        >
                                                            {isUrging ? (
                                                                <Loader2 className="h-4 w-4 animate-spin text-warning" />
                                                            ) : (
                                                                <BellRing className="h-4 w-4 group-hover/urge:animate-bounce" />
                                                            )}
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>催办此流程 (AI将提醒审批人)</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button
                                                            size="icon"
                                                            variant="ghost"
                                                            onClick={() => setRecallingId(item.id)}
                                                            className="h-8 w-8 rounded-full hover:bg-muted-foreground/10 hover:text-muted-foreground"
                                                        >
                                                            <Undo2 className="h-4 w-4" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>撤回此申请</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                            </>
                                        )}

                                        {canResubmit && (
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => openResubmit(item)}
                                                            className="h-7 text-xs gap-1"
                                                        >
                                                            <RefreshCw className="h-3 w-3" />
                                                            重新提交
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>修改后重新提交审批</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                        )}

                                        <div className={cn("flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider", status.color)}>
                                            {status.icon}
                                            {status.label}
                                        </div>
                                    </div>

                                    <div className="text-muted-foreground flex-shrink-0">
                                        {isExpanded ? (
                                            <ChevronUp className="w-4 h-4" />
                                        ) : (
                                            <ChevronDown className="w-4 h-4" />
                                        )}
                                    </div>
                                </div>
                                {isExpanded && (
                                    <div className="bg-secondary/20 border-x border-b border-border/30 rounded-b-xl -mt-2 pt-2">
                                        <HistoryItemProgress requestId={item.id} />
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            {/* 撤回确认弹窗 */}
            <AlertDialog open={!!recallingId} onOpenChange={() => setRecallingId(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>确认撤回</AlertDialogTitle>
                        <AlertDialogDescription>
                            撤回后该审批将终止流转，确定要撤回吗？
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>取消</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleRecallConfirm}
                            disabled={recallMutation.isPending}
                        >
                            {recallMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
                            确认撤回
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            {/* 重新提交弹窗 */}
            <Dialog open={!!resubmittingItem} onOpenChange={() => setResubmittingItem(null)}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>重新提交审批</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 pt-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">申请事由</label>
                            <Textarea
                                value={resubmitDesc}
                                onChange={(e) => setResubmitDesc(e.target.value)}
                                placeholder="修改申请事由..."
                                className="min-h-24 resize-none"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">金额</label>
                            <Input
                                type="number"
                                value={resubmitAmount}
                                onChange={(e) => setResubmitAmount(e.target.value)}
                                placeholder="修改金额（可选）"
                                min={0}
                            />
                        </div>
                        <div className="flex justify-end gap-3">
                            <Button variant="outline" onClick={() => setResubmittingItem(null)}>取消</Button>
                            <Button
                                onClick={handleResubmit}
                                disabled={resubmitMutation.isPending}
                            >
                                {resubmitMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
                                重新提交
                            </Button>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>

            {/* 审批详情弹窗（只读） */}
            <ApprovalDetailDialog
                item={detailItem as Parameters<typeof ApprovalDetailDialog>[0]['item']}
                open={!!detailItem}
                onClose={() => setDetailItem(null)}
            />
        </div>
    );
}
