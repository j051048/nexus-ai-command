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
        <div className="relative overflow-hidden card-glass rounded-3xl p-6 sm:p-8 border border-border/50 transition-all duration-300 h-full">
            <div className="absolute -top-10 -right-10 w-40 h-40 bg-primary/10 blur-[50px] rounded-full mix-blend-screen pointer-events-none animate-pulse-glow" />
            
            <div className="flex items-center justify-between mb-8 relative z-10">
                <div>
                    <h2 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-foreground to-foreground/80">团队绩效矩阵</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">AI 多维综合评分图谱 (实时)</p>
                </div>
                <button className="px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-xs font-semibold hover:bg-primary hover:text-white transition-all duration-300 flex items-center gap-1.5 shadow-sm">
                    深度解析 <ChevronRight className="w-3.5 h-3.5" />
                </button>
            </div>

            <div className="space-y-3 relative z-10">
                <div className="flex items-center gap-3 text-xs font-semibold text-muted-foreground uppercase tracking-widest pl-24 mb-2">
                    <div className="flex-1 grid grid-cols-5 gap-3 text-center">
                        <span>周一</span>
                        <span>周二</span>
                        <span>周三</span>
                        <span>周四</span>
                        <span>周五</span>
                    </div>
                </div>
                {data.map((member, index) => (
                    <div 
                        key={member.name} 
                        className="flex items-center gap-3 animate-fade-slide-right"
                        style={{ animationDelay: `${index * 100}ms` }}
                    >
                        <div className="w-20 text-sm font-medium text-foreground text-right truncate">{member.name}</div>
                        <div className="flex-1 grid grid-cols-5 gap-3">
                            {[member.mon, member.tue, member.wed, member.thu, member.fri].map((score, idx) => (
                                <div
                                    key={idx}
                                    className="relative group cursor-crosshair"
                                >
                                    <div className={cn(
                                        "h-10 rounded-xl flex items-center justify-center text-sm font-bold shadow-sm transition-all duration-300 hover:scale-110 hover:-translate-y-1 hover:z-10",
                                        score >= 90 ? "bg-gradient-success text-white ring-2 ring-success/30 glow-success" :
                                        score >= 80 ? "bg-gradient-primary text-white ring-1 ring-primary/30" :
                                        score >= 70 ? "bg-gradient-warning text-white ring-1 ring-warning/30" :
                                        "bg-background/50 backdrop-blur-sm border border-border text-muted-foreground hover:bg-destructive hover:text-white"
                                    )}>
                                        {score}
                                    </div>
                                    
                                    {/* Tooltip on hover */}
                                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max px-2 py-1 bg-foreground text-background text-xs font-bold rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20 shadow-xl">
                                        基于 {score} 项数据评估
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>

            <div className="flex items-center justify-center gap-6 mt-8 relative z-10 p-3 bg-background/30 backdrop-blur-md rounded-2xl border border-border/50">
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-md bg-gradient-success glow-success" />
                    <span className="text-xs font-semibold text-foreground">卓越 (&ge;90)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-md bg-gradient-primary" />
                    <span className="text-xs font-semibold text-foreground">优秀 (80-89)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-md bg-gradient-warning" />
                    <span className="text-xs font-semibold text-foreground">达标 (70-79)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-md bg-background/50 border border-border" />
                    <span className="text-xs font-semibold text-foreground">异常 (&lt;70)</span>
                </div>
            </div>
        </div>
    );
}
