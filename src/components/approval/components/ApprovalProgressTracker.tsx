import React from 'react';
import { cn } from '@/lib/utils';
import {
    CheckCircle2,
    XCircle,
    Clock,
    Zap,
    Bell,
    Mail,
    Timer,
    UserCheck,
    GitBranch,
} from 'lucide-react';

// ---- Types ----

interface ApprovalStep {
    id: string;
    type: string; // 'approver' | 'condition' | 'auto_approve' | 'notify' | 'cc_notify' | 'timer'
    label: string;
    role?: string;
    timeout_hours?: number;
}

interface ApprovalHistoryEntry {
    step: number;
    decision: string;
    approver_id: string;
    approver_name?: string;
    timestamp: string;
}

export interface ApprovalProgressTrackerProps {
    steps: ApprovalStep[];
    currentStep: number;
    approvalHistory: ApprovalHistoryEntry[];
    status: 'pending' | 'approved' | 'rejected';
}

// ---- Helpers ----

const STEP_ICON_MAP: Record<string, React.ReactNode> = {
    approver: <UserCheck className="w-4 h-4" />,
    condition: <GitBranch className="w-4 h-4" />,
    auto_approve: <Zap className="w-4 h-4" />,
    notify: <Bell className="w-4 h-4" />,
    cc_notify: <Mail className="w-4 h-4" />,
    timer: <Timer className="w-4 h-4" />,
};

function getStepIcon(type: string) {
    return STEP_ICON_MAP[type] || <UserCheck className="w-4 h-4" />;
}

function getHistoryForStep(
    stepIndex: number,
    history: ApprovalHistoryEntry[]
): ApprovalHistoryEntry | undefined {
    return history.find((h) => h.step === stepIndex);
}

function formatTimestamp(ts: string): string {
    try {
        const d = new Date(ts);
        return d.toLocaleString('zh-CN', {
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch {
        return ts;
    }
}

// ---- Component ----

export function ApprovalProgressTracker({
    steps,
    currentStep,
    approvalHistory,
    status,
}: ApprovalProgressTrackerProps) {
    if (!steps || steps.length === 0) {
        return null;
    }

    return (
        <div className="w-full overflow-x-auto py-4">
            <div className="flex items-start min-w-max px-2">
                {steps.map((step, index) => {
                    const historyEntry = getHistoryForStep(index, approvalHistory);
                    const isCompleted = index < currentStep;
                    const isCurrent = index === currentStep;
                    const isFuture = index > currentStep;
                    const isRejected = status === 'rejected' && isCurrent;
                    const isLast = index === steps.length - 1;

                    // Determine step status for styling
                    let stepStatus: 'completed' | 'current' | 'rejected' | 'future' = 'future';
                    if (isRejected) {
                        stepStatus = 'rejected';
                    } else if (isCompleted) {
                        stepStatus = 'completed';
                    } else if (isCurrent) {
                        stepStatus = 'current';
                    }

                    return (
                        <React.Fragment key={step.id}>
                            {/* Step node */}
                            <div className="flex flex-col items-center min-w-[100px] max-w-[120px]">
                                {/* Circle */}
                                <div
                                    className={cn(
                                        'w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all',
                                        stepStatus === 'completed' &&
                                            'bg-success/10 border-success text-success',
                                        stepStatus === 'current' &&
                                            'bg-primary/10 border-primary text-primary animate-pulse',
                                        stepStatus === 'rejected' &&
                                            'bg-destructive/10 border-destructive text-destructive',
                                        stepStatus === 'future' &&
                                            'bg-muted border-border text-muted-foreground'
                                    )}
                                >
                                    {stepStatus === 'completed' && (
                                        <CheckCircle2 className="w-5 h-5" />
                                    )}
                                    {stepStatus === 'rejected' && (
                                        <XCircle className="w-5 h-5" />
                                    )}
                                    {stepStatus === 'current' && !isRejected && (
                                        getStepIcon(step.type)
                                    )}
                                    {stepStatus === 'future' && (
                                        getStepIcon(step.type)
                                    )}
                                </div>

                                {/* Label */}
                                <p
                                    className={cn(
                                        'text-xs font-medium mt-2 text-center leading-tight',
                                        stepStatus === 'completed' && 'text-success',
                                        stepStatus === 'current' && 'text-primary',
                                        stepStatus === 'rejected' && 'text-destructive',
                                        stepStatus === 'future' && 'text-muted-foreground'
                                    )}
                                >
                                    {step.label}
                                </p>

                                {/* Sub-info: approver name + timestamp for completed */}
                                {isCompleted && historyEntry && (
                                    <div className="mt-1 text-center">
                                        {historyEntry.approver_name && (
                                            <p className="text-[10px] text-muted-foreground">
                                                {historyEntry.approver_name}
                                            </p>
                                        )}
                                        <p className="text-[10px] text-muted-foreground">
                                            {historyEntry.decision === 'approved' ? '已批' : '已处理'}
                                        </p>
                                        <p className="text-[10px] text-muted-foreground/70">
                                            {formatTimestamp(historyEntry.timestamp)}
                                        </p>
                                    </div>
                                )}

                                {/* Current step hint */}
                                {isCurrent && !isRejected && (
                                    <p className="text-[10px] text-primary mt-1">
                                        当前等待
                                    </p>
                                )}

                                {/* Rejected step hint */}
                                {isRejected && historyEntry && (
                                    <div className="mt-1 text-center">
                                        {historyEntry.approver_name && (
                                            <p className="text-[10px] text-destructive">
                                                {historyEntry.approver_name}
                                            </p>
                                        )}
                                        <p className="text-[10px] text-destructive">
                                            已驳回
                                        </p>
                                        <p className="text-[10px] text-muted-foreground/70">
                                            {formatTimestamp(historyEntry.timestamp)}
                                        </p>
                                    </div>
                                )}

                                {/* Future step hint */}
                                {isFuture && (
                                    <p className="text-[10px] text-muted-foreground/50 mt-1">
                                        未到达
                                    </p>
                                )}

                                {/* Timeout hint */}
                                {step.timeout_hours && step.timeout_hours > 0 && isCurrent && (
                                    <div className="flex items-center gap-0.5 mt-1">
                                        <Clock className="w-3 h-3 text-warning" />
                                        <span className="text-[10px] text-warning">
                                            {step.timeout_hours}h超时
                                        </span>
                                    </div>
                                )}
                            </div>

                            {/* Connecting line (except after last step) */}
                            {!isLast && (
                                <div className="flex items-center pt-5 mx-1">
                                    <div
                                        className={cn(
                                            'h-0.5 w-10 transition-colors',
                                            index < currentStep
                                                ? 'bg-success'
                                                : index === currentStep && status === 'rejected'
                                                ? 'bg-destructive'
                                                : index === currentStep
                                                ? 'bg-primary'
                                                : 'bg-border'
                                        )}
                                    />
                                    <div
                                        className={cn(
                                            'w-0 h-0 border-t-[5px] border-t-transparent border-b-[5px] border-b-transparent border-l-[6px]',
                                            index < currentStep
                                                ? 'border-l-success'
                                                : index === currentStep && status === 'rejected'
                                                ? 'border-l-destructive'
                                                : index === currentStep
                                                ? 'border-l-primary'
                                                : 'border-l-border'
                                        )}
                                    />
                                </div>
                            )}
                        </React.Fragment>
                    );
                })}
            </div>
        </div>
    );
}
