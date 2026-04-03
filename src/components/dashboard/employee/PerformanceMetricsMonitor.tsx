import React from 'react';
import { cn } from '@/lib/utils';

interface Metric {
    name: string;
    value: number;
    target: number;
    unit: string;
    status: 'excellent' | 'good' | 'warning';
}

interface PerformanceMetricsMonitorProps {
    metrics: Metric[];
}

export function PerformanceMetricsMonitor({ metrics }: PerformanceMetricsMonitorProps) {
    return (
        <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 sm:mb-6">
                <h2 className="text-base sm:text-lg font-semibold text-foreground">绩效指标实时监控</h2>
                <span className="flex items-center gap-1 text-xs text-success">
                    <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
                    实时更新
                </span>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
                {(Array.isArray(metrics) ? metrics : []).map((metric) => (
                    <div key={metric.name} className="space-y-2 sm:space-y-3">
                        <div className="flex items-center justify-between gap-1">
                            <p className="text-xs sm:text-sm text-muted-foreground truncate">{metric.name}</p>
                            <span className={cn(
                                "text-xs font-medium px-1.5 sm:px-2 py-0.5 rounded-full flex-shrink-0",
                                metric.status === 'excellent' && "bg-success/20 text-success",
                                metric.status === 'good' && "bg-primary/20 text-primary",
                                metric.status === 'warning' && "bg-warning/20 text-warning"
                            )}>
                                {metric.status === 'excellent' ? '优秀' : metric.status === 'good' ? '达标' : '待提升'}
                            </span>
                        </div>
                        <div className="flex items-baseline gap-1">
                            <span className="text-xl sm:text-2xl font-bold text-foreground mono-number">{metric.value}</span>
                            <span className="text-xs sm:text-sm text-muted-foreground">{metric.unit}</span>
                            <span className="text-xs text-muted-foreground ml-1 hidden sm:inline">/ {metric.target}{metric.unit}</span>
                        </div>
                        <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                            <div
                                className={cn(
                                    "h-full rounded-full transition-all duration-500",
                                    metric.value >= metric.target ? "bg-success" : "bg-warning"
                                )}
                                style={{ width: `${Math.min((metric.value / metric.target) * 100, 100)}%` }}
                            />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
