import React from 'react';
import { cn } from '@/lib/utils';

interface RankingItem {
    rank: number;
    name: string;
    score: number;
    bonus: number;
    isCurrentUser?: boolean;
}

interface WeeklyRankingsProps {
    rankings: RankingItem[];
}

export function WeeklyRankings({ rankings }: WeeklyRankingsProps) {
    return (
        <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-base sm:text-lg font-semibold text-foreground">本周排行榜</h2>
                <span className="text-xs text-muted-foreground">实时更新</span>
            </div>
            <div className="space-y-2 sm:space-y-3">
                {rankings.map((item) => (
                    <div
                        key={item.rank}
                        className={cn(
                            "flex items-center gap-2 sm:gap-3 p-2 sm:p-3 rounded-xl transition-colors",
                            item.isCurrentUser ? "bg-primary/10 border border-primary/30" : "hover:bg-secondary"
                        )}
                    >
                        <div className={cn(
                            "w-7 h-7 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center text-xs sm:text-sm font-bold flex-shrink-0",
                            item.rank === 1 && "rank-gold",
                            item.rank === 2 && "rank-silver",
                            item.rank === 3 && "rank-bronze",
                            item.rank > 3 && "bg-secondary text-muted-foreground"
                        )}>
                            {item.rank}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className={cn(
                                "text-sm font-medium truncate",
                                item.isCurrentUser ? "text-primary" : "text-foreground"
                            )}>
                                {item.name} {item.isCurrentUser && "(我)"}
                            </p>
                        </div>
                        <div className="text-right flex-shrink-0">
                            <p className="text-sm font-bold text-foreground mono-number">{item.score}</p>
                            <p className="text-xs text-success mono-number">¥{item.bonus.toLocaleString()}</p>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
