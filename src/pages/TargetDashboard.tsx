/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Target,
    TrendingUp,
    Users,
    Calendar,
    Trophy,
    ArrowUpRight,
    Flame,
    Zap,
    Briefcase
} from "lucide-react";
import { useUser } from "@/contexts/UserContext";

const MOCK_TARGETS = [
    { title: "月度销售额", current: 850000, target: 1200000, unit: "元", icon: <TrendingUp className="w-4 h-4" /> },
    { title: "线索转化率", current: 18, target: 25, unit: "%", icon: <Target className="w-4 h-4" /> },
    { title: "客户拜访量", current: 42, target: 40, unit: "次", icon: <Users className="w-4 h-4" /> },
];

export function TargetDashboard() {
    const { user } = useUser();

    return (
        <div className="space-y-8 max-w-7xl mx-auto pb-20">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex flex-col gap-2">
                    <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                        <Target className="w-8 h-8 text-primary" />
                        个人目标看板
                    </h1>
                    <p className="text-muted-foreground">距离您的月度目标还剩 5 个工作日，请查收 AI 复期策略</p>
                </div>
                <div className="flex items-center gap-2 bg-primary/10 px-4 py-2 rounded-2xl border border-primary/20">
                    <Flame className="w-5 h-5 text-orange-500 animate-pulse" />
                    <span className="text-sm font-bold text-primary">当前排位: 第 3 名</span>
                </div>
            </div>

            {/* Top Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {MOCK_TARGETS.map((target) => {
                    const progress = Math.min(100, Math.floor((target.current / target.target) * 100));
                    return (
                        <Card key={target.title} className="hover:shadow-md transition-all overflow-hidden relative">
                            {progress >= 100 && (
                                <div className="absolute top-[-20px] right-[-20px] bg-success p-3 rounded-full text-white rotate-12 z-10 shadow-lg">
                                    <Trophy className="w-4 h-4" />
                                </div>
                            )}
                            <CardHeader className="pb-2">
                                <div className="flex justify-between items-center bg-secondary/30 p-2 rounded-lg mb-2">
                                    {target.icon}
                                    <Badge variant={progress >= 100 ? "default" : "secondary"}>
                                        {progress >= 100 ? "已超额" : "进行中"}
                                    </Badge>
                                </div>
                                <CardTitle className="text-sm font-medium text-muted-foreground">
                                    {target.title}
                                </CardTitle>
                                <div className="flex items-baseline gap-1 mt-2">
                                    <span className="text-3xl font-extrabold">{target.current.toLocaleString()}</span>
                                    <span className="text-xs text-muted-foreground">/ {target.target.toLocaleString()} {target.unit}</span>
                                </div>
                            </CardHeader>
                            <CardContent className="pt-4">
                                <div className="space-y-2">
                                    <div className="flex justify-between text-xs font-bold">
                                        <span className={progress >= 100 ? "text-success" : "text-primary"}>完成度 {progress}%</span>
                                        <span className="text-muted-foreground">{target.current >= target.target ? "目标达成" : "差额 " + (target.target - target.current).toLocaleString()}</span>
                                    </div>
                                    <Progress value={progress} className={`h-2 ${progress >= 100 ? 'bg-success/20' : ''}`} />
                                </div>
                            </CardContent>
                        </Card>
                    );
                })}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* AI Improvement Column */}
                <Card className="lg:col-span-2 border-primary/20 bg-gradient-to-br from-primary/10 to-transparent">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Zap className="w-5 h-5 text-primary" /> AI 补位策略建议
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="bg-white/50 dark:bg-black/20 p-6 rounded-2xl border border-border shadow-inner">
                            <h4 className="font-bold flex items-center gap-2 mb-4">
                                <TrendingUp className="w-4 h-4 text-primary" /> 业绩差距分析
                            </h4>
                            <p className="text-sm text-foreground leading-relaxed mb-6">
                                您现在的销售额缺口为 **35 万**。根据近期线索分析，您有以下三个机会点可以快速补齐：
                            </p>
                            <div className="space-y-4">
                                <div className="p-4 bg-card rounded-xl border border-border flex items-center justify-between group cursor-pointer hover:border-primary/50 transition-colors">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-success/10 text-success">
                                            <ArrowUpRight className="w-4 h-4" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-bold">加快成交：某生物实验室扩建项目</p>
                                            <p className="text-xs text-muted-foreground">预计额度：12万 | 客户处于比价阶段，建议跟进</p>
                                        </div>
                                    </div>
                                    <Button size="sm" variant="ghost" className="opacity-0 group-hover:opacity-100">立即行动</Button>
                                </div>

                                <div className="p-4 bg-card rounded-xl border border-border flex items-center justify-between group cursor-pointer hover:border-primary/50 transition-colors">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-primary/10 text-primary">
                                            <Briefcase className="w-4 h-4" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-bold">激活沉睡线索：去年的年度维保客户</p>
                                            <p className="text-xs text-muted-foreground">预计额度：8万 | 已到期未续约，AI 已为您整理话术</p>
                                        </div>
                                    </div>
                                    <Button size="sm" variant="ghost" className="opacity-0 group-hover:opacity-100">立即行动</Button>
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Performance Calendar / History */}
                <Card className="lg:col-span-1">
                    <CardHeader>
                        <CardTitle className="text-sm font-bold flex items-center gap-2 uppercase tracking-tighter">
                            <Calendar className="w-4 h-4 text-muted-foreground" /> 本周战绩走势
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-64 flex items-end justify-between gap-2 px-2">
                            {[12, 18, 45, 32, 65, 54, 88].map((h, i) => (
                                <div key={i} className="flex-1 group relative">
                                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-black text-white text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                                        积分 +{h}
                                    </div>
                                    <div
                                        className="w-full bg-primary/30 group-hover:bg-primary transition-all rounded-t-md"
                                        style={{ height: `${h}%` }}
                                    />
                                    <span className="text-[10px] text-muted-foreground block text-center mt-2">
                                        {['一', '二', '三', '四', '五', '六', '日'][i]}
                                    </span>
                                </div>
                            ))}
                        </div>
                        <div className="mt-8 p-4 bg-secondary/30 rounded-xl border border-border">
                            <div className="flex items-center gap-2 mb-2">
                                <Trophy className="w-4 h-4 text-gold" />
                                <span className="text-sm font-bold">今日战绩评价</span>
                            </div>
                            <p className="text-xs text-muted-foreground italic">"今天您成交了 1 笔较大订单，排名本周积分激增榜榜首！继续保持。"</p>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
