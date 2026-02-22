/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ListChecks, Bot, Loader2, Upload, AlertCircle, CheckCircle2, FileText, ArrowRight } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { toast } from "sonner";
import { useUser } from "@/contexts/UserContext";
import { AICopilotInsight } from '@/components/common/AICopilotInsight';

export function TenderAnalysisPage() {
    const { user } = useUser();
    const [file, setFile] = useState<File | null>(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [currentStep, setCurrentStep] = useState(0);
    const [report, setReport] = useState<string | null>(null);
    const [docId, setDocId] = useState<string | null>(null);
    const [progress, setProgress] = useState(0);
    const [analysisStartTime, setAnalysisStartTime] = useState(0);

    const steps = [
        "上传并建立索引...",
        "提取否决性条款...",
        "合规性大模型比对...",
        "生成诊断报告..."
    ];

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setReport(null);
            setCurrentStep(0);
            setDocId(null);
            setProgress(0);
        }
    };

    const handleStartAnalysis = async () => {
        if (!file) return;
        setAnalyzing(true);
        setCurrentStep(0);
        setProgress(0);
        setReport(null);
        setAnalysisStartTime(Date.now());

        try {
            // Step 1: Upload with robust URL discovery (same as DocumentsPage)
            const formData = new FormData();
            formData.append('files', file);
            if (user?.id) {
                formData.append('userId', user.id);
            }

            // Robust URL Discovery
            let url = '';
            const configuredUrl = import.meta.env.VITE_API_BASE_URL;
            if (configuredUrl) {
                url = configuredUrl.startsWith('http') ? configuredUrl : `https://${configuredUrl}`;
            } else {
                url = window.location.hostname === 'localhost' ? 'http://localhost:8000' : window.location.origin;
            }
            const endpoint = `${url.replace(/\/$/, '')}/api/documents/upload`;

            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;

            if (!token) {
                toast.error('请先登录');
                setAnalyzing(false);
                return;
            }

            const uploadRes = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData,
                mode: 'cors',
            }).catch(err => {
                console.error('Fetch error details:', err);
                throw new Error(`网络连接异常: 无法触达后端 [${endpoint}]。请确认后端服务已启动。`);
            });

            if (!uploadRes.ok) {
                const errorBody = await uploadRes.json().catch(() => ({}));
                throw new Error(errorBody.message || errorBody.reason || `上传失败 (HTTP ${uploadRes.status})`);
            }

            const uploadData = await uploadRes.json();

            // Backend returns StandardResponse: { success, data: { results: [...] } }
            const results = uploadData.data?.results || uploadData.results;
            const firstResult = results?.[0];

            if (firstResult?.status === 'error') {
                throw new Error(firstResult.reason || firstResult.message || 'AI 解析文档失败');
            }

            if (firstResult?.status === 'duplicate') {
                toast.warning(firstResult.message || '文件内容与已有文档重复');
                setAnalyzing(false);
                return;
            }

            if (firstResult?.document_id) {
                setDocId(firstResult.document_id);
                toast.info("文档已上传，AI 分析启动...");
            } else {
                throw new Error("上传返回异常，未获取到文档 ID");
            }

        } catch (error) {
            console.error(error);
            const message = error instanceof Error ? error.message : '上传处理异常，请重试';
            toast.error(message);
            setAnalyzing(false);
        }
    };

    // Polling for Progress (exponential backoff: 2s → 4s → 8s cap)
    useEffect(() => {
        if (!docId || !analyzing) return;

        let cancelled = false;
        let delay = 2000; // initial 2s
        const MAX_DELAY = 8000;

        const poll = async () => {
            if (cancelled) return;

            const { data, error } = await supabase
                .from('documents')
                .select('status, progress, stage, extracted_data')
                .eq('id', docId)
                .single();

            if (cancelled) return;

            const doc = data;

            if (error) {
                console.error("Polling error:", error);
            }

            if (doc) {
                const prog = doc.progress || 0;
                setProgress(prog);

                // Map Progress to Steps
                if (prog < 30) setCurrentStep(0);
                else if (prog < 60) setCurrentStep(1);
                else if (prog < 90) setCurrentStep(2);
                else setCurrentStep(3);

                if (doc.status === 'ready' || doc.status === 'success') {
                    generateReport(doc.extracted_data);
                    setAnalyzing(false);
                    toast.success("AI 诊断完成");
                    return; // stop polling
                } else if (doc.status === 'failed' || doc.status === 'error') {
                    setAnalyzing(false);
                    toast.error("AI 分析过程中发生错误");
                    return; // stop polling
                } else if (Date.now() - analysisStartTime > 180000) { // 3 minutes timeout
                    setAnalyzing(false);
                    toast.error("AI 分析响应超时，请重试");
                    return; // stop polling
                }
            }

            // Schedule next poll with exponential backoff
            delay = Math.min(delay * 2, MAX_DELAY);
            if (!cancelled) {
                setTimeout(poll, delay);
            }
        };

        // Start first poll after initial delay
        const timer = setTimeout(poll, delay);

        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [docId, analyzing]);

    const generateReport = (data: any) => {
        if (!data) return;

        // 优先使用后端生成的高质量 Markdown 报告
        if (data.full_analysis_markdown) {
            setReport(data.full_analysis_markdown);
            return;
        }

        const redlines = data.redlines?.map((r: string) => `- 🚨 ${r}`).join('\n') || "- 未发现明显否决性条款";
        const deviations = data.technical_deviations?.map((d: string) => `- ⚠️ ${d}`).join('\n') || "- 未发现明显技术偏离";
        const tags = data.tags?.join(', ') || "无标签";

        const md = `### 📋 标书分析报告 - ${file?.name}\n\n` +
            `**文档类型**: ${data.doc_type || '未知'}\n` +
            `**摘要**: ${data.summary || '无摘要'}\n` +
            `**标签**: ${tags}\n\n` +
            `#### 🚨 否决性条款 (Redlines)\n${redlines}\n\n` +
            `#### 🛠️ 技术偏离建议 (Deviations)\n${deviations}\n\n` +
            `> *注意：此报告由 AI 生成，仅供参考，请以人工复核为准。*`;

        setReport(md);
    };

    const handleExportPDF = async () => {
        const element = document.getElementById('analysis-report-content');
        if (!element || !report) return;

        try {
            toast.dismiss();
            toast.info("正在生成 PDF，请稍候...", { duration: 2000 });

            const html2canvas = (await import('html2canvas')).default;
            const { jsPDF } = await import('jspdf');

            const canvas = await html2canvas(element, {
                scale: 2, // Higher resolution
                useCORS: true,
                logging: false,
                backgroundColor: '#ffffff'
            });

            const imgData = canvas.toDataURL('image/png');
            const pdf = new jsPDF('p', 'mm', 'a4');
            const pdfWidth = pdf.internal.pageSize.getWidth();
            const pdfHeight = pdf.internal.pageSize.getHeight();

            const imgWidth = canvas.width;
            const imgHeight = canvas.height;

            // Scale content to fit PDF width (minus margins)
            const margin = 10;
            const contentWidth = pdfWidth - (margin * 2);
            const contentHeight = (imgHeight * contentWidth) / imgWidth;

            let heightLeft = contentHeight;
            const pageHeight = pdfHeight - (margin * 2);

            // First page
            pdf.addImage(imgData, 'PNG', margin, margin, contentWidth, contentHeight);
            heightLeft -= pageHeight;

            // Add more pages if content is long
            while (heightLeft > 0) {
                pdf.addPage();
                // Simulating page break by just rendering negative offset
                // Note: Ideally we should slice the canvas, but negative offset is the quick hack for jsPDF
                pdf.addImage(imgData, 'PNG', margin, margin - (contentHeight - heightLeft), contentWidth, contentHeight);
                heightLeft -= pageHeight;
            }

            pdf.save(`${file?.name || '标书分析报告'}_analysis.pdf`);
            toast.success("PDF 已下载");

        } catch (error) {
            console.error("PDF Export Error:", error);
            toast.error("PDF 生成失败");
        }
    };

    return (
        <div className="space-y-6 max-w-5xl mx-auto pb-20">
            <div className="flex flex-col gap-2">
                <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
                    <ListChecks className="w-8 h-8 text-primary" />
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
                        <Button variant={file ? "default" : "secondary"} onClick={() => document.getElementById('tender-input')?.click()}>
                            {file ? "重新选择" : "选择文件"}
                        </Button>

                        {file && (
                            <Button className="w-full mt-4" onClick={handleStartAnalysis} disabled={analyzing}>
                                {analyzing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Bot className="w-4 h-4 mr-2" />}
                                {analyzing ? "AI 分析中..." : "开始 AI 诊断"}
                            </Button>
                        )}
                    </CardContent>
                </Card>

                {analyzing && (
                    <Card className="md:col-span-2">
                        <CardHeader>
                            <CardTitle>AI 处理进度 ({progress}%)</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="space-y-4">
                                {steps.map((step, index) => (
                                    <div key={index} className="flex items-center gap-3">
                                        {index < currentStep ? (
                                            <CheckCircle2 className="w-5 h-5 text-green-500" />
                                        ) : index === currentStep ? (
                                            <Loader2 className="w-5 h-5 animate-spin text-primary" />
                                        ) : (
                                            <div className="w-5 h-5 rounded-full border-2 border-muted" />
                                        )}
                                        <span className={index === currentStep ? "font-medium text-foreground" : "text-muted-foreground"}>
                                            {step}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                )}

                {report && !analyzing && (
                    <Card className="md:col-span-2 bg-muted/30">
                        <CardHeader className="flex flex-row items-center justify-between">
                            <CardTitle className="flex items-center gap-2">
                                <FileText className="w-5 h-5" />
                                诊断报告
                            </CardTitle>
                            <Button variant="outline" size="sm" onClick={handleExportPDF}>
                                导出 PDF
                            </Button>
                        </CardHeader>
                        <CardContent id="analysis-report-content" className="bg-background p-6 rounded-lg border shadow-sm mx-6 mb-6">
                            <AICopilotInsight
                                title="标书深度分析结论"
                                context="基于 Gemini-3 Pro 的全文扫描与条款比对"
                                insights={[]}
                                className="border-0 shadow-none bg-transparent p-0 mb-4"
                            />
                            <div className="markdown-body prose dark:prose-invert max-w-none">
                                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground">
                                    {report}
                                </pre>
                            </div>
                        </CardContent>
                    </Card>
                )}
            </div>
        </div>
    );
}
