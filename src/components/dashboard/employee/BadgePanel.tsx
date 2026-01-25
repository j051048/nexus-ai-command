import React from 'react';
import { cn } from '@/lib/utils';
import { ChevronRight, Star } from 'lucide-react';
import { Badge } from '@/types/nexus';

interface BadgePanelProps {
    badges: Badge[];
}

export function BadgePanel({ badges }: BadgePanelProps) {
    return (
        <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-base sm:text-lg font-semibold text-foreground">我的徽章</h2>
                <button className="text-xs text-primary hover:underline flex items-center gap-1">
                    查看全部 <ChevronRight className="w-3 h-3" />
                </button>
            </div>
            <div className="flex gap-2 sm:gap-4 overflow-x-auto pb-2">
                {badges.map((badge, index) => (
                    <div
                        key={badge.id}
                        className={cn(
                            "flex flex-col items-center gap-2 p-3 sm:p-4 rounded-xl transition-all flex-shrink-0",
                            badge.tier === 'gold' && "bg-gold/10",
                            badge.tier === 'silver' && "bg-silver/10",
                            badge.tier === 'bronze' && "bg-bronze/10",
                            index === 0 && "badge-unlock"
                        )}
                    >
                        <span className="text-2xl sm:text-3xl">{badge.icon}</span>
                        <span className="text-xs font-medium text-foreground whitespace-nowrap">{badge.name}</span>
                        <span className={cn(
                            "text-xs px-2 py-0.5 rounded-full",
                            badge.tier === 'gold' && "rank-gold",
                            badge.tier === 'silver' && "rank-silver",
                            badge.tier === 'bronze' && "rank-bronze"
                        )}>
                            {badge.tier === 'gold' ? '金' : badge.tier === 'silver' ? '银' : '铜'}
                        </span>
                    </div>
                ))}
                <div className="flex flex-col items-center justify-center gap-2 p-3 sm:p-4 rounded-xl border-2 border-dashed border-border opacity-50 flex-shrink-0">
                    <Star className="w-6 h-6 sm:w-8 sm:h-8 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">待解锁</span>
                </div>
            </div>
        </div>
    );
}
