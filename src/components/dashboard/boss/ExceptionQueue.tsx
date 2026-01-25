import React from 'react';
import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { ApprovalRequestSafe } from '@/lib/schemas';

interface ExceptionQueueProps {
    pendingApprovals: ApprovalRequestSafe[];
    onApprove: (id: string) => void;
    onReject: (id: string) => void;
    isProcessing: boolean;
}

export function ExceptionQueue({
    pendingApprovals,
    onApprove,
    onReject,
    isProcessing
}: ExceptionQueueProps) {
    return (
        <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 sm:mb-6">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-warning/20 flex items-center justify-center">
                        <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 text-warning" />
                    </div>
                    <div>
                        <h2 className="text-base sm:text-lg font-semibold text-foreground">异常待办 (实时)</h2>
                        <p className="text-xs text-muted-foreground">仅显示需人工介入的审批</p>
                    </div>
                </div>
                <span className="text-sm text-muted-foreground">
                    共 <span className="text-warning font-semibold">{pendingApprovals.length}</span> 条
                </span>
            </div>

            {pendingApprovals.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                    <CheckCircle2 className="w-8 h-8 mx-auto mb-2 opacity-50 text-success" />
                    <p>当前没有待处理的异常审批</p>
                </div>
            ) : (
                <div className="space-y-3 sm:space-y-4">
                    {pendingApprovals.map((item) => (
                        <div
                            key={item.id}
                            className="p-3 sm:p-4 rounded-xl border border-warning/50 bg-warning/5 transition-colors hover:bg-secondary/50"
                        >
                            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                                        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-warning/20 text-warning">
                                            {item.type === 'expense' ? '报销' : '采购'}
                                        </span>
                                        <h3 className="font-medium text-foreground text-sm sm:text-base">
                                            {item.description || '无描述'}
                                        </h3>
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-xs text-muted-foreground mt-2">
                                        <span>申请人：{item.submitter_name}</span>
                                        <span>金额：<span className="text-foreground font-medium">¥{item.amount.toLocaleString()}</span></span>
                                        <span>时间：{new Date(item.created_at).toLocaleString()}</span>
                                    </div>
                                </div>
                                <div className="flex gap-2 flex-shrink-0">
                                    <button
                                        onClick={() => onReject(item.id)}
                                        disabled={isProcessing}
                                        className="px-3 sm:px-4 py-2 rounded-lg bg-destructive/20 text-destructive text-xs sm:text-sm font-medium hover:bg-destructive/30 transition-colors flex items-center gap-1"
                                    >
                                        <XCircle className="w-4 h-4" />
                                        驳回
                                    </button>
                                    <button
                                        onClick={() => onApprove(item.id)}
                                        disabled={isProcessing}
                                        className="px-3 sm:px-4 py-2 rounded-lg bg-success text-white text-xs sm:text-sm font-medium hover:bg-success/90 transition-colors flex items-center gap-1"
                                    >
                                        <CheckCircle2 className="w-4 h-4" />
                                        批准
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
