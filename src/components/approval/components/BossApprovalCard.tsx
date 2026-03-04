import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import {
    CheckCircle2,
    XCircle,
    Bot,
    Loader2,
    ChevronDown,
    ChevronUp,
    ShieldAlert,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ApprovalRequest, useApprovalProgress } from '@/hooks/useApprovals';
import { DynamicFormRenderer } from '@/components/forms/DynamicFormRenderer';
import { useFormSchema } from '@/hooks/useFormSchemas';
import type { FormField } from '@/components/forms/DynamicFormRenderer';
import { ApprovalProgressTracker } from './ApprovalProgressTracker';

const statusConfig = {
    pending: { label: '待处理', color: 'bg-warning/20 text-warning', icon: <CheckCircle2 className="w-4 h-4" /> },
    approved: { label: '已批准', color: 'bg-success/20 text-success', icon: <CheckCircle2 className="w-4 h-4" /> },
    rejected: { label: '已驳回', color: 'bg-destructive/20 text-destructive', icon: <XCircle className="w-4 h-4" /> },
};

const approvalTypesIcons: Record<string, React.ReactNode> = {
    travel: <CheckCircle2 className="w-5 h-5" />, // These will be passed or mapped
    purchase: <CheckCircle2 className="w-5 h-5" />,
    expense: <CheckCircle2 className="w-5 h-5" />,
    leave: <CheckCircle2 className="w-5 h-5" />,
};

interface BossApprovalCardProps {
    approval: ApprovalRequest;
    onApprove: () => void;
    onReject: () => void;
    isApproving: boolean;
    typeIcon?: React.ReactNode;
    currentUserId?: string;
}

// ─── 表单数据只读展示组件 ────────────────────────────────────

function FormDataDisplay({ approval }: { approval: ApprovalRequest }) {
    const extendedApproval = approval as unknown as {
        form_data?: Record<string, unknown>;
        form_schema_id?: string;
    };

    const { data: schema } = useFormSchema(extendedApproval.form_schema_id || '');

    if (!extendedApproval.form_data || !extendedApproval.form_schema_id) {
        return null;
    }

    const fields: FormField[] = schema?.fields || [];

    if (fields.length === 0) {
        return null;
    }

    return (
        <div className="mt-3 p-3 rounded-lg bg-secondary/30 border border-border/50">
            <p className="text-xs font-medium text-muted-foreground mb-2">自定义表单详情</p>
            <DynamicFormRenderer
                fields={fields}
                values={extendedApproval.form_data}
                onChange={() => {}}
                readOnly
            />
        </div>
    );
}

// ─── AI 风险分析展示组件 ────────────────────────────────────

function AIRiskAnalysis({ requestId }: { requestId: string }) {
    const [isExpanded, setIsExpanded] = useState(false);
    const { data: progressData } = useApprovalProgress(requestId);

    const riskAnalysis = progressData?.risk_analysis;

    if (!riskAnalysis) {
        return null;
    }

    const riskColor = riskAnalysis.risk_score >= 70
        ? 'text-destructive'
        : riskAnalysis.risk_score >= 40
        ? 'text-warning'
        : 'text-success';

    return (
        <div className="mt-3 border border-border/50 rounded-lg overflow-hidden">
            <button
                type="button"
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center justify-between p-2.5 hover:bg-secondary/30 transition-colors"
            >
                <div className="flex items-center gap-2">
                    <ShieldAlert className={cn("w-4 h-4", riskColor)} />
                    <span className="text-xs font-medium text-foreground">AI 风险分析</span>
                    <span className={cn("text-xs font-bold", riskColor)}>
                        {riskAnalysis.risk_score}分
                    </span>
                </div>
                {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-muted-foreground" />
                ) : (
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                )}
            </button>
            {isExpanded && (
                <div className="p-3 pt-0 space-y-2 border-t border-border/50">
                    {/* Risk Score Bar */}
                    <div className="mt-2">
                        <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
                            <span>风险评分</span>
                            <span className={cn("font-bold", riskColor)}>
                                {riskAnalysis.risk_score}/100
                            </span>
                        </div>
                        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                            <div
                                className={cn(
                                    "h-full rounded-full transition-all",
                                    riskAnalysis.risk_score >= 70 ? 'bg-destructive' :
                                    riskAnalysis.risk_score >= 40 ? 'bg-warning' :
                                    'bg-success'
                                )}
                                style={{ width: `${riskAnalysis.risk_score}%` }}
                            />
                        </div>
                    </div>

                    {/* Compliance Flags */}
                    {riskAnalysis.compliance_flags.length > 0 && (
                        <div>
                            <p className="text-[10px] text-muted-foreground mb-1">合规标记</p>
                            <div className="flex flex-wrap gap-1">
                                {riskAnalysis.compliance_flags.map((flag, i) => (
                                    <span
                                        key={i}
                                        className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] bg-warning/10 text-warning font-medium"
                                    >
                                        {flag}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Historical Context */}
                    {riskAnalysis.historical_context && (
                        <div>
                            <p className="text-[10px] text-muted-foreground mb-1">历史分析</p>
                            <p className="text-xs text-foreground/80 leading-relaxed">
                                {riskAnalysis.historical_context}
                            </p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ─── 审批链进度展示组件 ────────────────────────────────────

function ApprovalChainProgress({ requestId }: { requestId: string }) {
    const { data: progressData, isLoading } = useApprovalProgress(requestId);

    if (isLoading || !progressData || !progressData.steps || progressData.steps.length === 0) {
        return null;
    }

    return (
        <div className="mt-3 p-2 rounded-lg bg-secondary/20 border border-border/30">
            <p className="text-[10px] font-medium text-muted-foreground mb-1 px-1">审批链进度</p>
            <ApprovalProgressTracker
                steps={progressData.steps}
                currentStep={progressData.current_step}
                approvalHistory={progressData.approval_history}
                status={progressData.status}
            />
        </div>
    );
}

// ─── 主组件 ──────────────────────────────────────────────────

export function BossApprovalCard({
    approval,
    onApprove,
    onReject,
    isApproving,
    typeIcon,
    currentUserId,
}: BossApprovalCardProps) {
    const status = statusConfig[approval.status as keyof typeof statusConfig] || statusConfig.pending;
    const isPending = approval.status === 'pending';
    const isSelfSubmitted = currentUserId && approval.submitted_by === currentUserId;

    return (
        <div className={cn(
            "p-4 rounded-xl border transition-colors",
            isPending ? "border-warning/50 bg-warning/5" : "border-border bg-secondary/50"
        )}>
            <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-4 flex-1">
                    <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
                        {typeIcon}
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                            <p className="font-medium text-foreground">{approval.description}</p>
                            <span className={cn("flex items-center gap-1 px-2 py-0.5 rounded-full text-xs", status.color)}>
                                {status.icon}
                                {status.label}
                            </span>
                        </div>
                        <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground flex-wrap">
                            <span>申请人：{approval.submitter_name}</span>
                            {/* 显示AI代提交标识 */}
                            {(approval as unknown as { submitted_via?: string }).submitted_via === 'ai_assistant' && (
                                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-purple-500/10 text-purple-500 font-medium">
                                    <Bot className="w-3 h-3" />
                                    豆豆代提交
                                </span>
                            )}
                            <span className="font-medium text-foreground">¥{approval.amount}</span>
                            <span>{new Date(approval.created_at).toLocaleString('zh-CN')}</span>
                        </div>
                        {approval.ai_reason && (
                            <div className="mt-2 p-2 rounded bg-primary/5 border border-primary/10">
                                <p className="text-xs text-muted-foreground flex items-center gap-1">
                                    <Bot className="w-3 h-3 text-primary" />
                                    <span className="font-semibold text-primary">AI 决策建议:</span> {approval.ai_reason}
                                </p>
                            </div>
                        )}
                        {approval.rejection_reason && (
                            <p className="text-xs text-destructive mt-2">
                                驳回原因：{approval.rejection_reason}
                            </p>
                        )}
                        {/* 自定义表单数据展示 */}
                        <FormDataDisplay approval={approval} />

                        {/* 审批链进度 */}
                        <ApprovalChainProgress requestId={approval.id} />

                        {/* AI 风险分析 */}
                        <AIRiskAnalysis requestId={approval.id} />
                    </div>
                </div>

                {isPending && !isSelfSubmitted && (
                    <div className="flex gap-2 flex-shrink-0">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onReject}
                            className="text-destructive hover:text-destructive"
                        >
                            <XCircle className="w-4 h-4 mr-1" />
                            驳回
                        </Button>
                        <Button
                            size="sm"
                            onClick={onApprove}
                            disabled={isApproving}
                            className="bg-success hover:bg-success/90"
                        >
                            {isApproving ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                                <CheckCircle2 className="w-4 h-4 mr-1" />
                            )}
                            批准
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
}
