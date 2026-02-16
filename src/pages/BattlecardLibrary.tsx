/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Swords, Search, Bot, Zap, ArrowRight, ShieldAlert, TrendingUp } from "lucide-react";
import { toast } from "sonner";


const COMMON_COMPETITORS = [
    { name: "安捷伦 (Agilent)", tag: "进口巨头", strength: "品牌响, 技术底蕴深", weakness: "价格高昂, 维护成本高" },
    { name: "赛默飞 (Thermo)", tag: "全线覆盖", strength: "产品线广, 生态完善", weakness: "售后响应慢, 定制化差" },
    { name: "岛津 (Shimadzu)", tag: "性价比高", strength: "耐用性好, 价格亲民", weakness: "高端市场竞争力弱" },
];

export function BattlecardLibrary() {
    const [searchTerm, setSearchTerm] = useState("");
    const [analyzing, setAnalyzing] = useState(false);
    const [selectedComp, setSelectedComp] = useState<any>(null);

    const handleSearch = (name: string) => {
        const compName = name || searchTerm;
        if (!compName) return;

        setAnalyzing(true);
        setSelectedComp({ name: compName });

        // TODO: 接入真实 AI 竞品分析 API（当前为 Mock 演示数据）
        // 查找本地预置数据或使用默认 mock
        const preset = COMMON_COMPETITORS.find(c => c.name === compName);

        setTimeout(() => {
            setSelectedComp({
                name: compName,
                tag: preset?.tag || "AI 分析",
                strength: preset?.strength || "市场份额占有率高，用户心智成熟",
                weakness: preset?.weakness || "底层架构老化，不支持最新 AI 联合调取",
                strategy: [
                    "强调我们的 10x 云端响应优势",
                    "对比长期维护合同，我们的年度成本低 30%",
                    "提供免费的旧系迁移服务",
                ],
            });
            setAnalyzing(false);
            toast.success(`已生成 ${compName} 的打击策略（演示数据）`);
        }, 800);
    };

    return (
        <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
            <div className="flex flex-col gap-2">
                <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
                    <Swords className="w-8 h-8 text-primary" />
                    竞品打击库 (Battlecards)
                    <Badge variant="secondary" className="text-xs ml-2">演示版</Badge>
                </h1>
                <p className="text-muted-foreground">知己知彼，AI 实时输出针对性打击策略与对比话术</p>
            </div>

            {/* Quick Search */}
            <div className="flex gap-2 max-w-2xl bg-card p-2 rounded-2xl shadow-sm border border-border">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                        placeholder="输入竞争对手名称 (如：赛默飞)..."
                        className="pl-10 border-none bg-transparent focus-visible:ring-0"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSearch(searchTerm)}
                    />
                </div>
                <Button onClick={() => handleSearch(searchTerm)} disabled={analyzing} className="bg-primary glow-primary font-bold">
                    {analyzing ? "AI 检索中..." : "生成打击卡"}
                </Button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
                {/* Left: Quick List */}
                <div className="lg:col-span-1 space-y-4">
                    <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider px-2">常用竞品</h3>
                    {COMMON_COMPETITORS.map((comp) => (
                        <Card
                            key={comp.name}
                            className="hover:border-primary/50 cursor-pointer group transition-all"
                            onClick={() => handleSearch(comp.name)}
                        >
                            <CardContent className="p-4 flex items-center justify-between">
                                <div className="space-y-1">
                                    <p className="font-bold text-foreground">{comp.name}</p>
                                    <Badge variant="secondary" className="text-[10px]">{comp.tag}</Badge>
                                </div>
                                <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all" />
                            </CardContent>
                        </Card>
                    ))}
                </div>

                {/* Right: Analysis Dashboard */}
                <div className="lg:col-span-3">
                    {selectedComp ? (
                        <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-500">
                            <Card className="bg-gradient-primary text-primary-foreground border-none shadow-xl glow-primary">
                                <CardContent className="p-8 flex items-center gap-6">
                                    <div className="p-4 rounded-3xl bg-white/20 backdrop-blur-md">
                                        <Swords className="w-10 h-10" />
                                    </div>
                                    <div>
                                        <h2 className="text-3xl font-extrabold mb-1">{selectedComp.name}</h2>
                                        <p className="opacity-80">针对性打击方案已由 AI 完成检索与比对</p>
                                    </div>
                                </CardContent>
                            </Card>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <Card className="border-l-4 border-l-success">
                                    <CardHeader>
                                        <CardTitle className="text-sm font-bold flex items-center gap-2">
                                            <TrendingUp className="w-4 h-4 text-success" /> 对手优势 (慎重对线)
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <p className="text-sm text-foreground leading-relaxed">{selectedComp.strength}</p>
                                    </CardContent>
                                </Card>

                                <Card className="border-l-4 border-l-destructive">
                                    <CardHeader>
                                        <CardTitle className="text-sm font-bold flex items-center gap-2">
                                            <ShieldAlert className="w-4 h-4 text-destructive" /> 对手劣势 (核心打击)
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <p className="text-sm text-foreground leading-relaxed">{selectedComp.weakness}</p>
                                    </CardContent>
                                </Card>
                            </div>

                            <Card className="border-primary/20 bg-primary/5">
                                <CardHeader>
                                    <CardTitle className="text-lg font-bold flex items-center gap-2">
                                        <Zap className="w-5 h-5 text-primary" /> AI 建议打击策略
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <ul className="space-y-4">
                                        {(selectedComp.strategy || ["正在提取深度对比文档..."]).map((s: string, i: number) => (
                                            <li key={i} className="flex items-start gap-3 text-sm">
                                                <div className="w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0 text-xs font-bold">
                                                    {i + 1}
                                                </div>
                                                <span className="text-foreground font-medium">{s}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </CardContent>
                            </Card>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-[500px] border-2 border-dashed rounded-3xl opacity-30">
                            <Bot className="w-16 h-16 mb-4" />
                            <p className="text-xl font-medium">在搜索框输入或选择左侧竞品开始分析</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
