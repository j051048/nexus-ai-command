import React from 'react';
import { cn } from '@/lib/utils';
import { ChevronRight } from 'lucide-react';

interface TeamHeatmapData {
    name: string;
    mon: number;
    tue: number;
    wed: number;
    thu: number;
    fri: number;
}

interface TeamPerformanceHeatmapProps {
    data: TeamHeatmapData[];
}

const getHeatColor = (score: number) => {
    if (score >= 90) return 'bg-success';
    if (score >= 80) return 'bg-primary';
    if (score >= 70) return 'bg-warning';
    return 'bg-destructive';
};

export function TeamPerformanceHeatmap({ data }: TeamPerformanceHeatmapProps) {
    return (
        <div className="bg-card rounded-2xl p-6 border border-border">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold text-foreground">团队绩效热力图</h2>
                <button className="text-xs text-primary hover:underline flex items-center gap-1">
                    详细分析 <ChevronRight className="w-3 h-3" />
                </button>
            </div>

            <div className="space-y-3">
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    <div className="w-20" />
                    <div className="flex-1 grid grid-cols-5 gap-2 text-center">
                        <span>周一</span>
                        <span>周二</span>
                        <span>周三</span>
                        <span>周四</span>
                        <span>周五</span>
                    </div>
                </div>
                {data.map((member) => (
                    <div key={member.name} className="flex items-center gap-3">
                        <div className="w-20 text-sm text-foreground truncate">{member.name}</div>
                        <div className="flex-1 grid grid-cols-5 gap-2">
                            {[member.mon, member.tue, member.wed, member.thu, member.fri].map((score, idx) => (
                                <div
                                    key={idx}
                                    className={cn(
                                        "h-8 rounded flex items-center justify-center text-xs font-medium text-white",
                                        getHeatColor(score)
                                    )}
                                >
                                    {score}
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>

            <div className="flex items-center justify-center gap-4 mt-4 text-xs">
                <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded bg-success" />
                    <span className="text-muted-foreground">≥90</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded bg-primary" />
                    <span className="text-muted-foreground">80-89</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded bg-warning" />
                    <span className="text-muted-foreground">70-79</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded bg-destructive" />
                    <span className="text-muted-foreground">&lt;70</span>
                </div>
            </div>
        </div>
    );
}
