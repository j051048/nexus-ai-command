import React from 'react';
import { Target, Sparkles, Phone, Mail } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SalesLead } from '@/types/nexus';

interface PriorityLeadsProps {
    leads: (SalesLead & { priority: string | number; reason: string })[]; // The mapped leads for today
}

export function PriorityLeads({ leads }: PriorityLeadsProps) {
    return (
        <div className="bg-gradient-card rounded-2xl p-6 cyber-border relative overflow-hidden group">
            {/* Background Decorative Element */}
            <div className="absolute -top-10 -right-10 w-40 h-40 bg-primary/5 rounded-full blur-3xl group-hover:bg-primary/10 transition-colors duration-1000" />

            <div className="flex items-center gap-3 mb-6 relative">
                <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center pulse-live shadow-lg shadow-primary/20">
                    <Target className="w-5 h-5 text-primary-foreground" />
                </div>
                <div>
                    <h2 className="text-lg font-bold text-foreground">今日 AI 战术推演</h2>
                    <p className="text-xs text-muted-foreground">基于全量数据挖掘出的最佳成交路径</p>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 relative">
                {leads.map((lead, index) => (
                    <div
                        key={lead.id}
                        className={cn(
                            "p-5 rounded-2xl border transition-all duration-300 hover:shadow-xl group/item",
                            index === 0
                                ? "border-primary/40 bg-primary/[0.03] scale-[1.02] shadow-sm"
                                : "border-border bg-card/50 hover:border-primary/30"
                        )}
                    >
                        <div className="flex items-start justify-between mb-4">
                            <div className={cn(
                                "w-9 h-9 rounded-xl flex items-center justify-center text-sm font-black shadow-inner",
                                index === 0 ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"
                            )}>
                                {lead.priority}
                            </div>
                            {index === 0 && (
                                <span className="px-2.5 py-1 text-[10px] font-black uppercase tracking-widest rounded-full bg-primary text-white flex items-center gap-1 shadow-sm">
                                    <Sparkles className="w-3 h-3" />
                                    最佳时机
                                </span>
                            )}
                        </div>

                        <h3 className="font-bold text-foreground text-sm group-hover/item:text-primary transition-colors">{lead.name}</h3>
                        <p className="text-xs text-muted-foreground mt-0.5 font-medium">{lead.company}</p>

                        <div className="mt-4 p-3 rounded-xl bg-background/50 border border-border/50 text-xs italic text-muted-foreground leading-relaxed">
                            "{lead.reason}"
                        </div>

                        <div className="flex gap-2 mt-5">
                            <button className="flex-1 py-2.5 rounded-xl bg-primary text-primary-foreground text-[10px] font-bold uppercase tracking-wider hover:opacity-90 transition-all flex items-center justify-center gap-1.5 shadow-sm active:scale-95">
                                <Phone className="w-3.5 h-3.5" />
                                立即突击
                            </button>
                            <button className="px-3.5 py-2.5 rounded-xl bg-secondary text-foreground text-[10px] hover:bg-secondary/80 border border-border transition-all active:scale-95">
                                <Mail className="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
