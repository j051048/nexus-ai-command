import React from 'react';
import { Trophy, Gift } from 'lucide-react';

interface StatCardsProps {
    rank: number;
    totalBonus: number;
}

export function StatCards({ rank, totalBonus }: StatCardsProps) {
    return (
        <>
            {/* Rank Card */}
            <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
                <div className="flex items-center gap-3 mb-3 sm:mb-4">
                    <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-gold/20 flex items-center justify-center">
                        <Trophy className="w-4 h-4 sm:w-5 sm:h-5 text-gold" />
                    </div>
                    <div className="min-w-0">
                        <p className="text-xs sm:text-sm text-muted-foreground">本周排名</p>
                        <p className="text-lg sm:text-2xl font-bold text-foreground">第 {rank} 名</p>
                    </div>
                </div>
                <p className="text-xs text-muted-foreground hidden sm:block">
                    距离第2名还差 <span className="text-primary font-medium">150</span> 分
                </p>
            </div>

            {/* Bonus Card */}
            <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
                <div className="flex items-center gap-3 mb-3 sm:mb-4">
                    <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-success/20 flex items-center justify-center">
                        <Gift className="w-4 h-4 sm:w-5 sm:h-5 text-success" />
                    </div>
                    <div className="min-w-0">
                        <p className="text-xs sm:text-sm text-muted-foreground">累计奖金</p>
                        <p className="text-lg sm:text-2xl font-bold text-success mono-number">
                            ¥{totalBonus.toLocaleString()}
                        </p>
                    </div>
                </div>
                <p className="text-xs text-muted-foreground hidden sm:block">
                    本月新增 <span className="text-success font-medium">¥2,200</span>
                </p>
            </div>
        </>
    );
}
