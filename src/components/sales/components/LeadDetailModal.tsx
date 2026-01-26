import React from 'react';
import { User, Sparkles, Phone, Mail, X } from 'lucide-react';
import { SalesLead } from '@/types/nexus';

interface LeadDetailModalProps {
    lead: SalesLead;
    onClose: () => void;
}

export function LeadDetailModal({ lead, onClose }: LeadDetailModalProps) {
    return (
        <div
            className="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={onClose}
        >
            <div
                className="bg-card rounded-2xl p-6 w-full max-w-lg border border-border shadow-2xl animate-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-start justify-between mb-6">
                    <div className="flex items-center gap-4">
                        <div className="w-14 h-14 rounded-xl bg-gradient-primary flex items-center justify-center shadow-lg shadow-primary/20">
                            <User className="w-7 h-7 text-primary-foreground" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-foreground">{lead.name}</h2>
                            <p className="text-muted-foreground font-medium">{lead.company}</p>
                            <p className="text-sm text-muted-foreground">{lead.title}</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-full hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground"
                    >
                        <X size={20} />
                    </button>
                </div>

                <div className="grid grid-cols-3 gap-4 mb-6">
                    <div className="p-4 rounded-xl bg-secondary/50 text-center border border-border/50 shadow-inner">
                        <p className="text-3xl font-bold text-foreground mono-number">{lead.winProbability}%</p>
                        <p className="text-[10px] text-muted-foreground uppercase tracking-wider mt-1 font-semibold">AI 赢率预测</p>
                    </div>
                    <div className="p-4 rounded-xl bg-secondary/50 text-center border border-border/50 shadow-inner">
                        <p className="text-3xl font-bold text-success mono-number">+{Math.floor(lead.winProbability / 10)}</p>
                        <p className="text-[10px] text-muted-foreground uppercase tracking-wider mt-1 font-semibold">绩效影响分</p>
                    </div>
                    <div className="p-4 rounded-xl bg-secondary/50 text-center border border-border/50 shadow-inner">
                        <p className="text-3xl font-bold text-primary mono-number">{lead.score}</p>
                        <p className="text-[10px] text-muted-foreground uppercase tracking-wider mt-1 font-semibold">线索评分</p>
                    </div>
                </div>

                <div className="p-4 rounded-xl bg-primary/5 border border-primary/20 mb-6 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-2 opacity-5">
                        <Sparkles size={40} className="text-primary" />
                    </div>
                    <div className="flex items-center gap-2 mb-2 relative">
                        <Sparkles className="w-4 h-4 text-primary" />
                        <span className="text-sm font-bold text-primary italic">AI 战术建议</span>
                    </div>
                    <p className="text-sm text-foreground leading-relaxed relative">{lead.aiSuggestion}</p>
                </div>

                <div className="flex gap-3 pt-2">
                    <button className="flex-1 py-3.5 rounded-xl bg-gradient-primary text-primary-foreground font-bold hover:opacity-90 shadow-lg shadow-primary/20 transition-all active:scale-95 flex items-center justify-center gap-2">
                        <Phone className="w-4 h-4" />
                        立即拨打
                    </button>
                    <button className="flex-1 py-3.5 rounded-xl bg-secondary text-foreground font-bold hover:bg-secondary/80 border border-border transition-all active:scale-95 flex items-center justify-center gap-2">
                        <Mail className="w-4 h-4" />
                        AI 邮件模板
                    </button>
                </div>
            </div>
        </div>
    );
}
