import React from 'react';
import { cn } from '@/lib/utils';

interface Performer {
    name: string;
    score: number;
    bonus: number;
}

interface TopPerformersProps {
    performers: Performer[];
}

export function TopPerformers({ performers }: TopPerformersProps) {
    return (
        <div className="relative overflow-hidden card-glass rounded-3xl p-6 sm:p-8 border border-border/50 transition-all duration-300 h-full">
            <div className="absolute top-0 right-0 w-32 h-32 bg-gold/10 blur-3xl rounded-full mix-blend-screen animate-pulse-glow pointer-events-none" />
            
            <div className="flex items-center justify-between mb-8 relative z-10">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gold/20">
                        <span className="text-xl">🏆</span>
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-foreground to-foreground/80">
                            本周之星
                        </h2>
                        <p className="text-sm text-muted-foreground mt-0.5">基于大模型深度绩效分析</p>
                    </div>
                </div>
            </div>

            <div className="space-y-4 relative z-10">
                {performers.map((performer, index) => (
                    <div
                        key={performer.name}
                        className={cn(
                            "relative overflow-hidden group flex items-center gap-4 p-4 rounded-2xl bg-background/40 backdrop-blur-md border border-border/50 transition-all duration-300 hover-lift hover:shadow-xl hover:bg-background/60",
                            index === 0 && "border-gold/40 shadow-[0_0_15px_rgba(250,204,21,0.15)] bg-gradient-to-r from-gold/5 to-transparent",
                            index === 1 && "border-silver/40 shadow-[0_0_15px_rgba(192,192,192,0.1)]",
                            index === 2 && "border-bronze/40"
                        )}
                        style={{ animationDelay: `${index * 150}ms` }}
                    >
                        {/* Glow effect on hover */}
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000" />
                        
                        <div className={cn(
                            "w-12 h-12 rounded-xl flex items-center justify-center text-lg font-bold shadow-lg relative z-10",
                            index === 0 ? "rank-gold ring-2 ring-gold/50 glow-warning" : "",
                            index === 1 ? "rank-silver ring-1 ring-silver/50" : "",
                            index === 2 ? "rank-bronze ring-1 ring-bronze/50" : "",
                            index > 2 ? "bg-secondary text-secondary-foreground" : ""
                        )}>
                            #{index + 1}
                        </div>
                        
                        <div className="flex-1 min-w-0 z-10">
                            <p className="font-bold text-foreground text-base truncate pr-2 group-hover:text-primary transition-colors">{performer.name}</p>
                            <div className="flex items-center gap-2 mt-1">
                                <span className="text-xs font-medium text-success bg-success/10 px-2 py-0.5 rounded-md">
                                    ¥{performer.bonus.toLocaleString()}
                                </span>
                                <span className="text-xs text-muted-foreground truncate">智能核定奖励</span>
                            </div>
                        </div>
                        
                        <div className="text-right z-10">
                            <p className={cn(
                                "text-3xl font-extrabold tracking-tight mono-number",
                                index === 0 ? "text-transparent bg-clip-text bg-gradient-to-br from-gold to-orange-400" : "text-foreground"
                            )}>
                                {performer.score}
                            </p>
                            <p className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground mt-0.5">XP Score</p>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
