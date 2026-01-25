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
        <div className="bg-card rounded-2xl p-6 border border-border">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold text-foreground">本周之星</h2>
                <span className="text-xs text-muted-foreground">按绩效分排名</span>
            </div>

            <div className="space-y-4">
                {performers.map((performer, index) => (
                    <div
                        key={performer.name}
                        className={cn(
                            "flex items-center gap-4 p-4 rounded-xl",
                            index === 0 && "bg-gold/10 border border-gold/30"
                        )}
                    >
                        <div className={cn(
                            "w-12 h-12 rounded-xl flex items-center justify-center text-lg font-bold",
                            index === 0 && "rank-gold",
                            index === 1 && "rank-silver",
                            index === 2 && "rank-bronze"
                        )}>
                            {index + 1}
                        </div>
                        <div className="flex-1">
                            <p className="font-medium text-foreground">{performer.name}</p>
                            <p className="text-sm text-muted-foreground">本周激励 ¥{performer.bonus.toLocaleString()}</p>
                        </div>
                        <div className="text-right">
                            <p className="text-2xl font-bold text-foreground mono-number">{performer.score}</p>
                            <p className="text-xs text-muted-foreground">绩效分</p>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
