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
        <div className="relative overflow-hidden glass rounded-3xl p-5 sm:p-8 cyber-border transition-all duration-300 h-full flex flex-col">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-warning to-transparent opacity-50" />
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 sm:mb-8 relative z-10">
                <div className="flex items-center gap-4">
                    <div className="relative">
                        <div className="absolute inset-0 bg-warning/20 rounded-2xl blur animate-pulse" />
                        <div className="relative w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-br from-warning/20 to-warning/5 border border-warning/30 flex items-center justify-center shadow-lg">
                            <AlertTriangle className="w-6 h-6 sm:w-7 sm:h-7 text-warning animate-bounce-subtle" />
                        </div>
                    </div>
                    <div>
                        <h2 className="text-xl sm:text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-foreground to-foreground/70">
                            异常决策列队
                        </h2>
                        <p className="text-sm font-medium text-muted-foreground flex items-center gap-2 mt-1">
                            <span className="flex h-2 w-2 rounded-full bg-warning animate-pulse" />
                            实时侦测拦截 · 等待人工复核
                        </p>
                    </div>
                </div>
                <div className="px-4 py-2 rounded-xl bg-background/50 backdrop-blur-sm border border-border/50 shadow-inner flex items-center gap-2">
                    <span className="text-sm font-medium text-muted-foreground">拦截总数</span>
                    <span className="text-xl font-bold text-warning mono-number">{pendingApprovals.length}</span>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto pr-2 relative z-10 custom-scrollbar">
                {pendingApprovals.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center py-12 text-muted-foreground bg-background/20 backdrop-blur-sm rounded-2xl border border-dashed border-border/50">
                        <div className="w-16 h-16 rounded-full bg-success/10 flex items-center justify-center mb-4">
                            <CheckCircle2 className="w-8 h-8 text-success" />
                        </div>
                        <p className="text-lg font-medium text-foreground">当前无拦截异常</p>
                        <p className="text-sm mt-1">AI 已全自动处理常规流程</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {pendingApprovals.map((item, index) => (
                            <div
                                key={item.id}
                                className="group relative p-4 sm:p-5 rounded-2xl border border-border/50 bg-background/40 backdrop-blur-md transition-all duration-300 hover:bg-background/60 hover-lift shadow-sm hover:shadow-xl"
                                style={{ animationDelay: `${index * 100}ms` }}
                            >
                                <div className="absolute inset-x-0 bottom-0 h-0.5 bg-gradient-to-r from-transparent via-warning/30 to-transparent scale-x-0 group-hover:scale-x-100 transition-transform duration-500" />
                                
                                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                    <div className="flex-1 min-w-0 space-y-2">
                                        <div className="flex items-center gap-3 flex-wrap">
                                            <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-warning/10 text-warning border border-warning/20 shadow-sm">
                                                {item.type === 'expense' ? '报销单异动' : '采购单异动'}
                                            </span>
                                            <h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight truncate">
                                                {item.description || '系统未提供事务描述'}
                                            </h3>
                                        </div>
                                        
                                        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground bg-background/30 px-3 py-2 rounded-xl w-fit">
                                            <span className="flex items-center gap-1.5">
                                                <span className="w-1.5 h-1.5 rounded-full bg-primary/50" />
                                                申请方: <span className="font-medium text-foreground">{item.submitter_name}</span>
                                            </span>
                                            <span className="flex items-center gap-1.5">
                                                <span className="w-1.5 h-1.5 rounded-full bg-success/50" />
                                                涉及金额: <span className="text-foreground font-bold font-mono">¥{item.amount.toLocaleString()}</span>
                                            </span>
                                            <span className="flex items-center gap-1.5">
                                                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50" />
                                                提交记录: <span>{new Date(item.created_at).toLocaleString()}</span>
                                            </span>
                                        </div>
                                    </div>
                                    
                                    <div className="flex gap-3 flex-shrink-0 mt-2 sm:mt-0">
                                        <button
                                            onClick={() => onReject(item.id)}
                                            disabled={isProcessing}
                                            className="px-4 py-2.5 rounded-xl bg-background/50 border border-destructive/30 text-destructive text-sm font-bold hover:bg-destructive hover:text-white transition-all duration-300 flex items-center gap-2 shadow-sm hover:glow-warning disabled:opacity-50 disabled:cursor-not-allowed group/btn"
                                        >
                                            <XCircle className="w-4 h-4 group-hover/btn:scale-110 transition-transform" />
                                            <span>阻断</span>
                                        </button>
                                        <button
                                            onClick={() => onApprove(item.id)}
                                            disabled={isProcessing}
                                            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-success to-success-glow text-white text-sm font-bold hover:brightness-110 transition-all duration-300 flex items-center gap-2 glow-success disabled:opacity-50 disabled:cursor-not-allowed group/btn"
                                        >
                                            <CheckCircle2 className="w-4 h-4 group-hover/btn:scale-110 transition-transform" />
                                            <span>放行</span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
