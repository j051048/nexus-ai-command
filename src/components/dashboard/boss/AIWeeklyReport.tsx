import React from 'react';
import { Bot, TrendingUp, AlertTriangle } from 'lucide-react';

interface WeeklyReport {
    cashFlow: number;
    cashFlowTrend: number;
    salesRisks: string[];
    totalIncentives: number;
    topPerformers: { name: string; score: number; bonus: number }[];
}

interface AIWeeklyReportProps {
    report: WeeklyReport;
}

export function AIWeeklyReport({ report }: AIWeeklyReportProps) {
    return (
        <div className="relative overflow-hidden glass rounded-3xl p-5 sm:p-8 cyber-border shadow-2xl transition-all duration-300">
            {/* Background glowing orb - Simplified static version for reduced noise */}
            <div className="absolute top-0 right-0 -mr-16 -mt-16 w-48 h-48 rounded-full bg-primary/5 blur-3xl pointer-events-none" />

            <div className="relative z-10 flex items-center gap-4 mb-6 sm:mb-8">
                <div className="relative">
                    <div className="relative w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-gradient-primary flex items-center justify-center glow-primary transition-transform hover:scale-105">
                        <Bot className="w-6 h-6 sm:w-7 sm:h-7 text-white" />
                    </div>
                </div>
                <div>
                    <h2 className="text-xl sm:text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-foreground to-foreground/70">
                        AI 周报摘要
                    </h2>
                    <p className="text-sm font-medium text-muted-foreground flex items-center gap-2 mt-1">
                        <span className="flex h-2 w-2 rounded-full bg-success pulse-live" />
                        本周自动生成 · 数据实时同步
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8 relative z-10">
                <div className="bg-background/40 backdrop-blur-md rounded-2xl p-4 border border-border/50 hover-lift">
                    <p className="text-xs sm:text-sm font-medium text-muted-foreground mb-2">预计本周现金流</p>
                    <div className="flex flex-col gap-1">
                        <span className="text-3xl sm:text-4xl font-extrabold text-foreground tracking-tight mono-number">
                            ¥{((report.cashFlow || 0) / 10000).toFixed(0)}<span className="text-xl sm:text-2xl text-muted-foreground ml-1">万</span>
                        </span>
                        <div className="flex items-center gap-1.5 text-success bg-success/10 w-fit px-2 py-1 rounded-md mt-1">
                            <TrendingUp className="w-4 h-4" />
                            <span className="text-xs font-bold">{report.cashFlowTrend || 0}%</span>
                        </div>
                    </div>
                </div>

                <div className="bg-background/40 backdrop-blur-md rounded-2xl p-4 border border-border/50 hover-lift relative overflow-hidden group">
                    <div className="absolute inset-0 bg-gradient-to-br from-warning/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                    <p className="text-xs sm:text-sm font-medium text-muted-foreground mb-2">AI检测销售风险</p>
                    <div className="flex items-baseline gap-2">
                        <span className="text-3xl sm:text-4xl font-extrabold text-warning tracking-tight mono-number">
                            {report.salesRisks.length}
                        </span>
                        <span className="text-sm font-medium text-muted-foreground">项异常</span>
                    </div>
                </div>

                <div className="bg-background/40 backdrop-blur-md rounded-2xl p-4 border border-border/50 hover-lift relative overflow-hidden group">
                    <div className="absolute inset-0 bg-gradient-to-br from-success/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                    <p className="text-xs sm:text-sm font-medium text-muted-foreground mb-2">本周智能激励发放</p>
                    <div className="flex flex-col gap-1">
                        <span className="text-3xl sm:text-4xl font-extrabold text-success tracking-tight mono-number">
                            <span className="text-xl sm:text-2xl text-success mr-1">¥</span>
                            {(report.totalIncentives / 10000).toFixed(1)}<span className="text-xl sm:text-2xl text-success ml-1">万</span>
                        </span>
                    </div>
                </div>

                <div className="bg-background/40 backdrop-blur-md rounded-2xl p-4 border border-border/50 hover-lift">
                    <p className="text-xs sm:text-sm font-medium text-muted-foreground mb-2">AI 自治处理率</p>
                    <div className="flex items-baseline gap-2">
                        <span className="text-3xl sm:text-4xl font-extrabold text-primary tracking-tight mono-number">95<span className="text-2xl">%</span></span>
                        <span className="text-sm font-medium text-primary">全程无人干预</span>
                    </div>
                </div>
            </div>

            {/* Risk Alerts */}
            {report.salesRisks.length > 0 && (
                <div className="mt-6 sm:mt-8 p-4 sm:p-5 bg-warning/5 backdrop-blur-sm rounded-2xl border border-warning/20 relative overflow-hidden z-10 animate-fade-slide-up" style={{ animationDelay: '300ms' }}>
                    <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-warning to-warning/20" />
                    <div className="flex items-center gap-2 mb-3 sm:mb-4">
                        <div className="p-1.5 rounded-full bg-warning/20 animate-pulse">
                            <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 text-warning" />
                        </div>
                        <span className="text-sm sm:text-base font-bold text-warning">Nexus AI 风险拦截警示</span>
                    </div>
                    <ul className="space-y-3">
                        {report.salesRisks.map((risk, index) => (
                            <li key={index} className="text-sm font-medium text-muted-foreground flex items-start gap-3 bg-background/40 p-3 rounded-xl hover:bg-background/60 transition-colors">
                                <span className="w-2 h-2 rounded-full bg-warning mt-1.5 flex-shrink-0 shadow-[0_0_8px_rgba(234,179,8,0.6)]" />
                                <span>{risk}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}
