import React from 'react';
import { cn } from '@/lib/utils';
import { SalesLead } from '@/types/nexus';
import { LeadCard } from '../components/LeadCard';

const stages = [
    { id: 'new', name: '新线索', color: 'bg-muted-foreground/50' },
    { id: 'contacted', name: '已联系', color: 'bg-primary/60' },
    { id: 'qualified', name: '已确认需求', color: 'bg-primary' },
    { id: 'proposal', name: '报价中', color: 'bg-warning' },
    { id: 'negotiation', name: '谈判中', color: 'bg-success' },
];

interface KanbanBoardProps {
    leads: SalesLead[];
    onLeadClick: (lead: SalesLead) => void;
}

export function KanbanBoard({ leads, onLeadClick }: KanbanBoardProps) {
    return (
        <div className="bg-card rounded-3xl p-6 border border-border shadow-sm" role="region" aria-label="销售管道看板">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h2 className="text-xl font-bold text-foreground">实时执行管道</h2>
                    <p className="text-xs text-muted-foreground mt-1">每个商机的状态及 AI 胜率分析已实时同步</p>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                        <span className="w-2 h-2 rounded-full bg-success animate-pulse" aria-hidden="true" />
                        AI 赢率算力已接入
                    </div>
                </div>
            </div>

            <div className="flex gap-6 overflow-x-auto pb-6 scrollbar-thin scrollbar-thumb-border" role="list" aria-label="销售阶段列表">
                {stages.map((stage) => {
                    const stageLeads = leads.filter(l => l.stage === stage.id);
                    return (
                        <div key={stage.id} className="flex-shrink-0 w-80 group/stage" role="listitem" aria-label={`${stage.name} - ${stageLeads.length} 条线索`}>
                            <div className="flex items-center justify-between mb-4 px-2">
                                <div className="flex items-center gap-2">
                                    <div className={cn("w-2 h-2 rounded-full shadow-sm", stage.color)} aria-hidden="true" />
                                    <span className="text-xs font-bold text-foreground/80 uppercase tracking-widest">{stage.name}</span>
                                    <span className="px-1.5 py-0.5 rounded-md bg-secondary text-[10px] font-bold text-muted-foreground" aria-label={`${stageLeads.length} 条`}>{stageLeads.length}</span>
                                </div>
                            </div>

                            <div className="space-y-4 min-h-[500px] p-2 rounded-2xl bg-secondary/20 border-2 border-dashed border-transparent group-hover/stage:border-border/30 transition-colors" role="list" aria-label={`${stage.name}阶段的线索`}>
                                {stageLeads.length === 0 ? (
                                    <div className="h-20 flex items-center justify-center border border-dashed border-border/50 rounded-xl opacity-20">
                                        <span className="text-[10px] uppercase font-bold tracking-tighter">无数据</span>
                                    </div>
                                ) : (
                                    stageLeads.map((lead) => (
                                        <LeadCard
                                            key={lead.id}
                                            lead={lead}
                                            onClick={() => onLeadClick(lead)}
                                        />
                                    ))
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
