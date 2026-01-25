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
        <div className="bg-gradient-card rounded-2xl p-4 sm:p-6 cyber-border">
            <div className="flex items-center gap-3 mb-4 sm:mb-6">
                <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-gradient-primary flex items-center justify-center">
                    <Bot className="w-4 h-4 sm:w-5 sm:h-5 text-primary-foreground" />
                </div>
                <div>
                    <h2 className="text-base sm:text-lg font-semibold text-foreground">AI 周报摘要</h2>
                    <p className="text-xs text-muted-foreground">本周自动生成 · 数据截至今日 09:00</p>
                </div>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
                <div className="space-y-2">
                    <p className="text-xs sm:text-sm text-muted-foreground">预计本周现金流</p>
                    <div className="flex items-baseline gap-2 flex-wrap">
                        <span className="text-2xl sm:text-3xl font-bold text-foreground mono-number">
                            ¥{(report.cashFlow / 10000).toFixed(0)}万
                        </span>
                        <span className="flex items-center text-success text-sm">
                            <TrendingUp className="w-4 h-4" />
                            {report.cashFlowTrend}%
                        </span>
                    </div>
                </div>

                <div className="space-y-2">
                    <p className="text-xs sm:text-sm text-muted-foreground">AI检测销售风险</p>
                    <div className="flex items-baseline gap-2">
                        <span className="text-2xl sm:text-3xl font-bold text-warning mono-number">
                            {report.salesRisks.length}
                        </span>
                        <span className="text-sm text-muted-foreground">条待关注</span>
                    </div>
                </div>

                <div className="space-y-2">
                    <p className="text-xs sm:text-sm text-muted-foreground">本周自动激励发放</p>
                    <div className="flex items-baseline gap-2">
                        <span className="text-2xl sm:text-3xl font-bold text-success mono-number">
                            ¥{report.totalIncentives.toLocaleString()}
                        </span>
                    </div>
                </div>

                <div className="space-y-2">
                    <p className="text-xs sm:text-sm text-muted-foreground">AI审批处理率</p>
                    <div className="flex items-baseline gap-2">
                        <span className="text-2xl sm:text-3xl font-bold text-primary mono-number">95%</span>
                        <span className="text-sm text-muted-foreground">自动通过</span>
                    </div>
                </div>
            </div>

            {/* Risk Alerts */}
            <div className="mt-4 sm:mt-6 p-3 sm:p-4 bg-warning/10 rounded-xl border border-warning/30">
                <div className="flex items-center gap-2 mb-2 sm:mb-3">
                    <AlertTriangle className="w-4 h-4 text-warning" />
                    <span className="text-sm font-medium text-warning">AI风险提醒</span>
                </div>
                <ul className="space-y-2">
                    {report.salesRisks.map((risk, index) => (
                        <li key={index} className="text-xs sm:text-sm text-muted-foreground flex items-start gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-warning mt-1.5 flex-shrink-0" />
                            <span>{risk}</span>
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
}
