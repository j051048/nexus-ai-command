import React, { useState } from 'react';
import { Clock, Loader2, CheckCircle2, XCircle, Bot, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ApprovalRequest, useApprovalProgress } from '@/hooks/useApprovals';
import { AICopilotInsight } from '@/components/common/AICopilotInsight';
import { ApprovalProgressTracker } from '../components/ApprovalProgressTracker';
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

    const toggleExpand = (id: string) => {
        setExpandedId((prev) => (prev === id ? null : id));
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
                        const status = statusConfig[item.status as keyof typeof statusConfig] || statusConfig.pending;
                        const typeInfo = approvalTypes.find(t => t.id === item.type);
                        const isExpanded = expandedId === item.id;

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
                                            {/* 显示AI代提交标识 */}
                                            {(item as unknown as { submitted_via?: string }).submitted_via === 'ai_assistant' && (
                                                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-purple-500/10 text-purple-500">
                                                    <Bot className="w-3 h-3" />
                                                    豆豆代提交
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    {item.amount > 0 && (
                                        <p className="text-sm font-bold text-foreground pr-2 font-mono">¥{item.amount.toLocaleString()}</p>
                                    )}
                                    <div className={cn("flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider", status.color)}>
                                        {status.icon}
                                        {status.label}
                                    </div>
                                    <div className="text-muted-foreground flex-shrink-0">
                                        {isExpanded ? (
                                            <ChevronUp className="w-4 h-4" />
                                        ) : (
                                            <ChevronDown className="w-4 h-4" />
                                        )}
                                    </div>
                                </div>
                                {/* Expandable progress tracker */}
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
        </div>
    );
}
