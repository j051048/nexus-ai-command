import React, { useState } from 'react';
import { Bot, Send, Loader2, Sparkles, CheckCircle2, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { useMyApprovals, useSubmitApproval } from '@/hooks/useApprovals';
import { approvalTypes } from '../constants';
import { ApprovalHistory } from './ApprovalHistory';

export function EmployeeApprovalView() {
    const [input, setInput] = useState('');
    const [amount, setAmount] = useState<number>(0);
    const [selectedType, setSelectedType] = useState<typeof approvalTypes[0] | null>(null);

    const { data: myApprovals, isLoading } = useMyApprovals();
    const submitApproval = useSubmitApproval();

    const handleSubmit = async () => {
        if (!input.trim() || !selectedType) {
            toast.error('请选择申请类型并填写说明');
            return;
        }

        try {
            const result = await submitApproval.mutateAsync({
                type: selectedType.id,
                description: input,
                amount,
            });

            if (result.status === 'approved') {
                toast.success('已自动审批通过！');
            } else {
                toast.success('已提交，等待老板审批');
            }

            setInput('');
            setAmount(0);
            setSelectedType(null);
        } catch (error: unknown) {
            const err = error as Error;
            toast.error('提交失败: ' + err.message);
        }
    };

    const applyExample = (type: typeof approvalTypes[0]) => {
        setSelectedType(type);
        setInput(type.example);
        const amountMatch = type.example.match(/(\d+)/);
        if (amountMatch) {
            setAmount(parseInt(amountMatch[1]));
        }
    };

    const stats = {
        total: myApprovals?.length || 0,
        approved: myApprovals?.filter(a => a.status === 'approved').length || 0,
        pending: myApprovals?.filter(a => a.status === 'pending').length || 0,
    };

    return (
        <div className="space-y-6">
            {/* Quick Submit Area */}
            <div className="bg-gradient-card rounded-2xl p-6 cyber-border relative overflow-hidden">
                <div className="absolute top-0 right-0 p-8 opacity-5 pointer-events-none">
                    <Bot size={120} />
                </div>

                <div className="flex items-center gap-3 mb-6 relative">
                    <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center pulse-live">
                        <Bot className="w-5 h-5 text-primary-foreground" />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold text-foreground">AI 智能申请</h2>
                        <p className="text-xs text-muted-foreground">支持自然语言描述，AI将自动为您分类并处理</p>
                    </div>
                </div>

                {/* Shortcuts */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6 relative">
                    {approvalTypes.map((type) => (
                        <button
                            key={type.id}
                            onClick={() => applyExample(type)}
                            className={cn(
                                "p-4 rounded-xl border transition-all text-left group",
                                selectedType?.id === type.id
                                    ? "border-primary bg-primary/10 shadow-sm"
                                    : "border-border bg-secondary/50 hover:border-primary/50"
                            )}
                        >
                            <div className={cn(
                                "w-10 h-10 rounded-lg flex items-center justify-center mb-3 group-hover:scale-110 transition-transform",
                                selectedType?.id === type.id ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                            )}>
                                {type.icon}
                            </div>
                            <p className="font-bold text-foreground text-sm">{type.name}</p>
                            <p className="text-[10px] text-muted-foreground mt-1">
                                AI 自动审批额度: ≤¥{type.threshold}
                            </p>
                        </button>
                    ))}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-4 gap-6 items-end relative">
                    <div className="sm:col-span-1 space-y-2">
                        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">金额 (¥)</label>
                        <Input
                            type="number"
                            value={amount}
                            onChange={(e) => setAmount(Number(e.target.value))}
                            placeholder="0.00"
                            className="bg-background/50"
                        />
                    </div>
                    <div className="sm:col-span-3 space-y-2 relative">
                        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">申请事由</label>
                        <div className="relative">
                            <Textarea
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder="例如：申请下周到深圳分公司举行产品发布会，预算4000元..."
                                className="min-h-24 resize-none pr-32 bg-background/50"
                            />
                            <Button
                                onClick={handleSubmit}
                                disabled={!input.trim() || !selectedType || submitApproval.isPending}
                                className="absolute bottom-3 right-3 shadow-lg shadow-primary/20"
                            >
                                {submitApproval.isPending ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <Send className="w-4 h-4 mr-2" />
                                )}
                                提交申请
                            </Button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Stats Quick Cards */}
            <div className="grid grid-cols-3 gap-4">
                {[
                    { label: '本月申请', value: stats.total, icon: <Clock />, bg: 'bg-primary/5', text: 'text-primary' },
                    { label: '已获批准', value: stats.approved, icon: <CheckCircle2 />, bg: 'bg-success/5', text: 'text-success' },
                    { label: '流程中', value: stats.pending, icon: <Sparkles />, bg: 'bg-warning/5', text: 'text-warning' },
                ].map((s, idx) => (
                    <div key={idx} className={cn("p-4 rounded-xl border border-border/50", s.bg)}>
                        <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-muted-foreground">{s.label}</span>
                            <span className={s.text}>{s.icon}</span>
                        </div>
                        <p className="text-2xl font-bold text-foreground">{s.value}</p>
                    </div>
                ))}
            </div>

            <ApprovalHistory approvals={myApprovals} isLoading={isLoading} />
        </div>
    );
}
