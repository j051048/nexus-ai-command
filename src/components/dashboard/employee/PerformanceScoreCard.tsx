import React from 'react';
import { TrendingUp, Award } from 'lucide-react';

interface PerformanceScoreCardProps {
    score: number;
    animatedScore: number;
    progressToNextBadge: number;
}

export function PerformanceScoreCard({
    score,
    animatedScore,
    progressToNextBadge
}: PerformanceScoreCardProps) {
    return (
        <div className="col-span-2 bg-gradient-card rounded-2xl p-4 sm:p-6 cyber-border">
            <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                    <p className="text-sm text-muted-foreground">今日AI绩效分</p>
                    <div className="flex items-baseline gap-2 mt-2">
                        <span className="text-3xl sm:text-5xl font-bold text-foreground mono-number score-up">
                            {animatedScore}
                        </span>
                        <span className="text-success text-sm font-medium flex items-center gap-1">
                            <TrendingUp className="w-4 h-4" />
                            +5
                        </span>
                    </div>
                    <div className="mt-4">
                        <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
                            <span className="truncate">距离"销售精英"徽章</span>
                            <span className="ml-2 flex-shrink-0">{100 - score} 分</span>
                        </div>
                        <div className="h-2 bg-secondary rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-primary rounded-full progress-fill"
                                style={{ width: `${progressToNextBadge}%` }}
                            />
                        </div>
                    </div>
                </div>
                <div className="w-14 h-14 sm:w-20 sm:h-20 rounded-2xl bg-gradient-primary flex items-center justify-center glow-primary flex-shrink-0">
                    <Award className="w-7 h-7 sm:w-10 sm:h-10 text-primary-foreground" />
                </div>
            </div>
        </div>
    );
}
