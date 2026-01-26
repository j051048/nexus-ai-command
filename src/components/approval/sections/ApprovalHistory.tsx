import React from 'react';
import { Clock, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ApprovalRequest } from '@/hooks/useApprovals';
import { AICopilotInsight } from '@/components/common/AICopilotInsight';
import { Plane, ShoppingCart, Receipt, Calendar as CalendarIcon } from 'lucide-react';

const approvalTypes = [
    { id: 'travel', icon: <Plane className="w-4 h-4" /> },
    { id: 'purchase', icon: <ShoppingCart className="w-4 h-4" /> },
    { id: 'expense', icon: <Receipt className="w-4 h-4" /> },
    { id: 'leave', icon: <CalendarIcon className="w-4 h-4" /> },
];

const statusConfig = {
    pending: { label: '待处理', color: 'bg-warning/20 text-warning', icon: <Clock className="w-3.5 h-3.5" /> },
    approved: { label: '已批准', color: 'bg-success/20 text-success', icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
    rejected: { label: '已驳回', color: 'bg-destructive/20 text-destructive', icon: <XCircle className="w-3.5 h-3.5" /> },
};

interface ApprovalHistoryProps {
    approvals?: ApprovalRequest[];
    isLoading: boolean;
}

export function ApprovalHistory({
    approvals,
    isLoading
}: ApprovalHistoryProps) {
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
                        const status = statusConfig[item.status as keyof typeof statusConfig] || statusConfig.pending;
                        const typeInfo = approvalTypes.find(t => t.id === item.type);

                        return (
                            <div
                                key={item.id}
                                className="flex items-center gap-4 p-4 rounded-xl bg-secondary/30 hover:bg-secondary/50 border border-transparent hover:border-border transition-all group"
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
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        {new Date(item.created_at).toLocaleString('zh-CN')}
                                    </p>
                                </div>
                                {item.amount > 0 && (
                                    <p className="text-sm font-bold text-foreground pr-2 font-mono">¥{item.amount.toLocaleString()}</p>
                                )}
                                <div className={cn("flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider", status.color)}>
                                    {status.icon}
                                    {status.label}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
