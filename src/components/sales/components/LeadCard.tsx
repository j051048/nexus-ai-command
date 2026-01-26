import React from 'react';
import { User, Building, Sparkles, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SalesLead } from '@/types/nexus';
import { AICopilotInsight } from '@/components/common/AICopilotInsight';

interface LeadCardProps {
    lead: SalesLead;
    onClick: () => void;
}

export function LeadCard({ lead, onClick }: LeadCardProps) {
    return (
        <div
            onClick={onClick}
            className="p-4 rounded-xl bg-secondary/50 border border-border hover:border-primary/50 transition-all cursor-pointer active-card group relative"
        >
            <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                        <User className="w-4 h-4 text-primary" />
                    </div>
                    <div className="min-w-0">
                        <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-foreground truncate">{lead.name}</p>
                            <AICopilotInsight
                                title={lead.name}
                                context={`Lead Score: ${lead.score}, Company: ${lead.company}`}
                                insights={[
                                    { type: 'summary', content: `该客户最近在官网上查看了 ${lead.company} 的产品参数。` },
                                    { type: 'suggestion', content: '建议提及我们在同行业的标杆案例以增加信任。' }
                                ]}
                                className="opacity-0 group-hover:opacity-100"
                            />
                        </div>
                        <p className="text-xs text-muted-foreground truncate">{lead.title}</p>
                    </div>
                </div>
                <div className="text-right shrink-0">
                    <p className="text-lg font-bold text-foreground mono-number">{lead.winProbability}%</p>
                    <p className="text-xs text-muted-foreground">赢率</p>
                </div>
            </div>

            <div className="flex items-center gap-1 text-xs text-muted-foreground mb-3">
                <Building className="w-3 h-3" />
                <span className="truncate">{lead.company}</span>
            </div>

            {/* AI Suggestion */}
            <div className="p-2 rounded-lg bg-primary/10 border border-primary/20">
                <div className="flex items-start gap-2">
                    <Sparkles className="w-3 h-3 text-primary mt-0.5 shrink-0" />
                    <p className="text-xs text-primary line-clamp-2 leading-relaxed">{lead.aiSuggestion}</p>
                </div>
            </div>

            {/* Score Impact */}
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-border">
                <span className="text-xs text-muted-foreground">绩效影响</span>
                <span className="text-xs text-success font-medium flex items-center gap-1">
                    <Zap className="w-3 h-3" />
                    +{Math.floor(lead.winProbability / 10)} 分
                </span>
            </div>
        </div>
    );
}
