import React, { useState } from 'react';
import {
    CheckCircle2,
    AlertTriangle,
    Sparkles,
    Loader2,
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
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
} from '@/hooks/useApprovals';
import { BossApprovalCard } from '../components/BossApprovalCard';
import { approvalTypes } from '../constants';

export function BossApprovalView() {
    const [statusFilter, setStatusFilter] = useState('pending');
    const [rejectingId, setRejectingId] = useState<string | null>(null);
    const [rejectReason, setRejectReason] = useState('');
    const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

    const { data: allApprovals, isLoading } = useAllApprovals(statusFilter);
    const { data: pendingCount } = usePendingApprovalsCount();
    const approveRequest = useApproveRequest();
    const rejectRequest = useRejectRequest();

    // A6: 移动端检测
    useEffect(() => {
        const handler = () => setIsMobile(window.innerWidth < 768);
        window.addEventListener('resize', handler);
        return () => window.removeEventListener('resize', handler);
    }, []);

    const handleApprove = async (requestId: string) => {
        try {
            await approveRequest.mutateAsync(requestId);
            toast.success('已批准该项申请');
        } catch (error: unknown) {
            const err = error as Error;
            toast.error('操作失败: ' + err.message);
        }
    };

    const handleReject = async () => {
        if (!rejectingId || !rejectReason.trim()) {
            toast.error('请填写驳回原因');
            return;
        }

        try {
            await rejectRequest.mutateAsync({ requestId: rejectingId, reason: rejectReason });
            toast.success('申请被驳回');
            setRejectingId(null);
            setRejectReason('');
        } catch (error: unknown) {
            const err = error as Error;
            toast.error('操作失败: ' + err.message);
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

                                            {/* A6: 移动端批准/驳回按钮 */}
                                            {approval.status === 'pending' && (
                                                <div className="flex gap-2 pt-2">
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => setRejectingId(approval.id)}
                                                        className="flex-1 text-destructive hover:text-destructive"
                                                    >
                                                        <XCircle className="w-4 h-4 mr-1" />
                                                        驳回
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        onClick={() => handleApprove(approval.id)}
                                                        disabled={approveRequest.isPending}
                                                        className="flex-1 bg-success hover:bg-success/90"
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
                                            )}
                                        </div>
                                    ) : (
                                        // A6: 桌面端保持原有组件
                                        <BossApprovalCard
                                            key={approval.id}
                                            approval={approval}
                                            onApprove={() => handleApprove(approval.id)}
                                            onReject={() => setRejectingId(approval.id)}
                                            isApproving={approveRequest.isPending}
                                            typeIcon={approvalTypes.find(t => t.id === approval.type)?.icon}
                                        />
                                    )
                                ))}
                            </div>
                        )}
                    </div>
                </TabsContent>
            </Tabs>

            {/* Reject Reason Dialog */}
            <Dialog open={!!rejectingId} onOpenChange={() => setRejectingId(null)}>
                <DialogContent className="max-w-md">
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
        </div>
    );
}
