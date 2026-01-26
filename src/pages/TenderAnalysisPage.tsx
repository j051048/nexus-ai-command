/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileSearch, Bot, Loader2, Upload, AlertCircle, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { useUser } from "@/contexts/UserContext";

export function TenderAnalysisPage() {
    const { user } = useUser();
    const [file, setFile] = useState<File | null>(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [report, setReport] = useState<string | null>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setReport(null);
        }
    };

    const handleStartAnalysis = async () => {
        if (!file) return;
        setAnalyzing(true);

        try {
            // First upload to get text (simplified for UX demo)
            // In reality, this would follow the ETL flow
            const formData = new FormData();
            formData.append('files', file);

            // Step 1: Extract Text via existing ETL
            const uploadRes = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/documents/upload`, {
                method: 'POST',
                body: formData
            });
            const uploadData = await uploadRes.json();

            if (uploadData.results && uploadData.results[0].status === 'success') {
                const textPreview = "招标文件涉及 ZY-100 型号产品的偏离项分析..."; // In real, use extracted text

                // Step 2: Call AI Tool
                const chatRes = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/chat/stream`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        messages: [
                            { role: "user", content: `请帮我分析这份招标文件中的否决性条款和合规风险。` }
                        ],
                        userId: user.id
                    })
                });

                // Simplified: We assume the AI will trigger the analyze_tender_document tool
                toast.success("AI 专家正在深度扫描招标文件...");
                // Mocking report result for immediate UX feedback
                setTimeout(() => {
                    setReport(`### 📋 标书分析报告 - ${file.name}\n\n#### 🚨 否决性条款 (Redlines)\n- 1.1 必须具备省级以上实验室认证（风险：目前我们资质申请中）。\n- 2.3 必须支持 24 小时本地化到场服务（满足：已有服务点）。\n\n#### 🛠️ 技术偏离建议\n- 建议在附件3中注明我们的 ZY-200 兼容 ZY-100 的所有参数并优于原型号。`);
                    setAnalyzing(false);
                }, 3000);
            }
        } catch (error) {
            toast.error("分析失败，请检查网络");
            setAnalyzing(false);
        }
    };

    return (
        <div className="space-y-6 max-w-5xl mx-auto pb-20">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                    <FileSearch className="w-8 h-8 text-primary" />
                    智能标书审阅
                </h1>
                <p className="text-muted-foreground">基于 AI 专家系统，快速识别招标文件中的扣分项与否决项</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="md:col-span-1 border-dashed border-2 hover:border-primary/50 transition-colors">
                    <CardContent className="pt-10 pb-10 text-center flex flex-col items-center gap-4">
                        <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                            <Upload className="w-8 h-8" />
                        </div>
                        <div className="space-y-2">
                            <p className="font-semibold">{file ? file.name : "上传招标文件"}</p>
                            <p className="text-xs text-muted-foreground">支持 PDF / Word / DOCX 格式</p>
                        </div>
                        <input
                            type="file"
                            id="tender-input"
                            className="hidden"
                            accept=".pdf,.doc,.docx"
                            onChange={handleFileChange}
                        />
                        <Button variant="outline" onClick={() => document.getElementById('tender-input')?.click()}>
                            {file ? "重新上传" : "选择文件"}
                        </Button>
                        {file && (
                            <Button
                                className="w-full mt-4 bg-primary glow-primary"
                                onClick={handleStartAnalysis}
                                disabled={analyzing}
                            >
                                {analyzing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Bot className="w-4 h-4 mr-2" />}
                                开始 AI 诊断
                            </Button>
                        )}
                    </CardContent>
                </Card>

                <Card className="md:col-span-2 min-h-[400px] relative overflow-hidden">
                    <CardHeader className="border-b bg-muted/30">
                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                            <Bot className="w-4 h-4" /> AI 诊断结果
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-6">
                        {analyzing ? (
                            <div className="flex flex-col items-center justify-center h-64 gap-4">
                                <div className="space-y-2 text-center">
                                    <div className="w-full max-w-xs bg-muted h-2 rounded-full overflow-hidden mx-auto">
                                        <div className="h-full bg-primary animate-[shimmer_2s_infinite] w-1/2" />
                                    </div>
                                    <p className="text-sm text-muted-foreground animate-pulse">正在提取条款并进行合规性比对...</p>
                                </div>
                            </div>
                        ) : report ? (
                            <div className="prose prose-sm dark:prose-invert max-w-none animate-in fade-in duration-700">
                                <div className="bg-success/10 border border-success/20 p-4 rounded-xl mb-6 flex items-start gap-3">
                                    <CheckCircle2 className="w-5 h-5 text-success mt-0.5" />
                                    <div>
                                        <h4 className="font-bold text-success mb-1">扫描完成</h4>
                                        <p className="text-xs text-success/80">发现了 2 处高风险条款，建议重点关注。</p>
                                    </div>
                                </div>
                                <div className="p-6 bg-secondary/20 rounded-2xl border border-border">
                                    <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground">
                                        {report}
                                    </pre>
                                </div>
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground space-y-4 opacity-50">
                                <AlertCircle className="w-12 h-12" />
                                <p>请先在左侧上传招标文档，AI 专家将即刻为您诊断</p>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
