/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ListChecks, Bot, Loader2, Upload, AlertCircle, CheckCircle2, FileText, ArrowRight, ChevronUp, ChevronDown, Clock, Eye, RotateCcw } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { toast } from "sonner";
import { useUser } from "@/contexts/UserContext";
import { AICopilotInsight } from '@/components/common/AICopilotInsight';

interface HistoryDoc {
    id: string;
    name: string;
    doc_type: string | null;
    status: string | null;
    extracted_data: any;
    owner_id: string | null;
    created_at: string;
    ownerName: string;
}

export function TenderAnalysisPage() {
    const { user } = useUser();
    const [file, setFile] = useState<File | null>(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [currentStep, setCurrentStep] = useState(0);
    const [report, setReport] = useState<string | null>(null);
    const [docId, setDocId] = useState<string | null>(null);
    const [progress, setProgress] = useState(0);
    const [analysisStartTime, setAnalysisStartTime] = useState(0);

    // History feature state
    const [historyDocs, setHistoryDocs] = useState<HistoryDoc[]>([]);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [showHistory, setShowHistory] = useState(true);
    const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);

    const steps = [
        "上传并建立索引...",
        "提取否决性条款...",
        "合规性大模型比对...",
        "生成诊断报告..."
    ];

    // --- History Functions ---

    const fetchHistory = useCallback(async () => {
        setHistoryLoading(true);
        try {
            const { data, error } = await (supabase.from('documents') as any)
                .select('id, name, doc_type, status, extracted_data, owner_id, created_at')
                .order('created_at', { ascending: false })
                .limit(20);

            if (error) throw error;

            // Filter to bid/tender documents (check both top-level and extracted_data.doc_type)
            const bidDocs = (data || []).filter((doc: any) => {
                const ed = typeof doc.extracted_data === 'string'
                    ? JSON.parse(doc.extracted_data)
                    : doc.extracted_data;
                return doc.doc_type === 'bid' || (ed && ed.doc_type === 'bid');
            });

            // Resolve owner names
            const ownerIds = [...new Set(bidDocs.map((d: any) => d.owner_id).filter(Boolean))] as string[];
            let nameMap: Record<string, string> = {};

            if (ownerIds.length > 0) {
                const { data: users } = await (supabase.from('users') as any)
                    .select('id, name')
                    .in('id', ownerIds);
                nameMap = Object.fromEntries(
                    (users || []).map((u: any) => [u.id, u.name || '未知用户'])
                );
            }

            const withNames: HistoryDoc[] = bidDocs.map((d: any) => ({
                ...d,
                extracted_data: typeof d.extracted_data === 'string'
                    ? JSON.parse(d.extracted_data)
                    : (d.extracted_data || {}),
                ownerName: d.owner_id === user?.id
                    ? '我'
                    : (nameMap[d.owner_id || ''] || '未知用户'),
            }));

            setHistoryDocs(withNames);
        } catch (err) {
            console.error('Failed to fetch tender history:', err);
        } finally {
            setHistoryLoading(false);
        }
    }, [user?.id]);

    // Fetch history on mount
    useEffect(() => {
        fetchHistory();
    }, [fetchHistory]);

    const handleLoadFromHistory = (histDoc: HistoryDoc) => {
        // Processing → resume polling
        if (histDoc.status === 'processing' || histDoc.status === 'pending') {
            setDocId(histDoc.id);
            setAnalyzing(true);
            setAnalysisStartTime(Date.now());
            setFile(null);
            setSelectedHistoryId(histDoc.id);
            toast.info('该文档仍在分析中，正在同步进度...');
            return;
        }

        // Failed
        if (histDoc.status === 'failed' || histDoc.status === 'error') {
            toast.error('该文档分析失败，无法查看报告');
            return;
        }

        // Ready — load report directly
        setSelectedHistoryId(histDoc.id);
        setDocId(histDoc.id);
        setFile(null);
        setAnalyzing(false);
        setProgress(100);
        setCurrentStep(3);

        generateReport(histDoc.extracted_data, histDoc.name);
        toast.success(`已加载「${histDoc.name}」的分析报告`);
    };

    const handleResetToNew = () => {
        setReport(null);
        setDocId(null);
        setSelectedHistoryId(null);
        setFile(null);
        setProgress(0);
        setCurrentStep(0);
        setAnalyzing(false);
    };

    // --- Core Functions ---

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setReport(null);
            setCurrentStep(0);
            setDocId(null);
            setProgress(0);
            setSelectedHistoryId(null);
        }
    };

    const handleStartAnalysis = async () => {
        if (!file) return;
        setAnalyzing(true);
        setCurrentStep(0);
        setProgress(0);
        setReport(null);
        setSelectedHistoryId(null);
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

            // Duplicate: auto-load existing analysis instead of just warning
            if (firstResult?.status === 'duplicate') {
                const existingDocId = firstResult.existing_document_id;

                if (existingDocId) {
                    toast.info('检测到相同文件，正在加载已有分析报告...');

                    const { data: existingDoc, error } = await supabase
                        .from('documents')
                        .select('id, name, status, extracted_data')
                        .eq('id', existingDocId)
                        .single();

                    if (error || !existingDoc) {
                        toast.error('加载已有文档失败，请刷新重试');
                        setAnalyzing(false);
                        return;
                    }

                    const ed = typeof (existingDoc as any).extracted_data === 'string'
                        ? JSON.parse((existingDoc as any).extracted_data)
                        : ((existingDoc as any).extracted_data || {});

                    if ((existingDoc as any).status === 'ready' || (existingDoc as any).status === 'success') {
                        setDocId(existingDocId);
                        setSelectedHistoryId(existingDocId);
                        generateReport(ed, (existingDoc as any).name);
                        setAnalyzing(false);
                        setProgress(100);
                        setCurrentStep(3);
                        fetchHistory();
                        toast.success(`已加载「${(existingDoc as any).name}」的分析报告`);
                    } else if ((existingDoc as any).status === 'processing' || (existingDoc as any).status === 'pending') {
                        setDocId(existingDocId);
                        setSelectedHistoryId(existingDocId);
                        toast.info('该文档正在分析中，已自动跟踪进度...');
                    } else {
                        toast.error('该文件之前的分析失败，请使用新文件名重试');
                        setAnalyzing(false);
                    }
                } else {
                    toast.warning(firstResult.message || '文件内容与已有文档重复');
                    setAnalyzing(false);
                }
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
                const prog = (doc as any).progress || 0;
                setProgress(prog);

                // Map Progress to Steps
                if (prog < 30) setCurrentStep(0);
                else if (prog < 60) setCurrentStep(1);
                else if (prog < 90) setCurrentStep(2);
                else setCurrentStep(3);

                if ((doc as any).status === 'ready' || (doc as any).status === 'success') {
                    generateReport((doc as any).extracted_data);
                    setAnalyzing(false);
                    setSelectedHistoryId(docId);
                    toast.success("AI 诊断完成");
                    fetchHistory(); // Refresh history list
                    return; // stop polling
                } else if ((doc as any).status === 'failed' || (doc as any).status === 'error') {
                    setAnalyzing(false);
                    toast.error("AI 分析过程中发生错误");
                    fetchHistory();
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

    const generateReport = (data: any, docName?: string) => {
        if (!data) return;

        // 优先使用后端生成的高质量 Markdown 报告
        if (data.full_analysis_markdown) {
            setReport(data.full_analysis_markdown);
            return;
        }

        const redlines = data.redlines?.map((r: string) => `- 🚨 ${r}`).join('\n') || "- 未发现明显否决性条款";
        const deviations = data.technical_deviations?.map((d: string) => `- ⚠️ ${d}`).join('\n') || "- 未发现明显技术偏离";
        const tags = data.tags?.join(', ') || "无标签";

        const md = `### 📋 标书分析报告 - ${docName || file?.name || '未知文档'}\n\n` +
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
                pdf.addImage(imgData, 'PNG', margin, margin - (contentHeight - heightLeft), contentWidth, contentHeight);
                heightLeft -= pageHeight;
            }

            const currentDocName = historyDocs.find(d => d.id === selectedHistoryId)?.name || file?.name || '标书分析报告';
            pdf.save(`${currentDocName}_analysis.pdf`);
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

            {/* History Panel */}
            <Card className="border border-border/50">
                <CardHeader
                    className="flex flex-row items-center justify-between py-3 px-6 cursor-pointer hover:bg-muted/30 transition-colors"
                    onClick={() => setShowHistory(!showHistory)}
                >
                    <CardTitle className="text-base flex items-center gap-2 font-medium">
                        <Clock className="w-4 h-4 text-muted-foreground" />
                        历史分析记录
                        {historyDocs.length > 0 && (
                            <Badge variant="secondary" className="ml-1 text-xs">
                                {historyDocs.length}
                            </Badge>
                        )}
                    </CardTitle>
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); setShowHistory(!showHistory); }}>
                        {showHistory ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </Button>
                </CardHeader>

                {showHistory && (
                    <CardContent className="pt-0 px-6 pb-4">
                        {historyLoading ? (
                            <div className="flex items-center justify-center py-6">
                                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                                <span className="ml-2 text-sm text-muted-foreground">加载中...</span>
                            </div>
                        ) : historyDocs.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                                <FileText className="w-10 h-10 opacity-20 mb-2" />
                                <p className="text-sm">暂无历史记录</p>
                                <p className="text-xs mt-1">上传标书文件开始 AI 诊断</p>
                            </div>
                        ) : (
                            <div className="space-y-2 max-h-64 overflow-y-auto">
                                {historyDocs.map((doc) => (
                                    <div
                                        key={doc.id}
                                        className={`flex items-center justify-between p-3 rounded-lg border transition-all cursor-pointer hover:bg-muted/50 ${
                                            selectedHistoryId === doc.id
                                                ? 'border-primary/50 bg-primary/5'
                                                : 'border-border/50'
                                        }`}
                                        onClick={() => handleLoadFromHistory(doc)}
                                    >
                                        <div className="flex items-center gap-3 min-w-0 flex-1">
                                            <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                                            <div className="min-w-0 flex-1">
                                                <p className="text-sm font-medium truncate">{doc.name}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    {doc.ownerName} · {new Date(doc.created_at).toLocaleDateString('zh-CN')}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                                            {doc.status === 'ready' || doc.status === 'success' ? (
                                                <Badge variant="default" className="bg-green-100 text-green-700 hover:bg-green-100 dark:bg-green-900/30 dark:text-green-400">
                                                    <CheckCircle2 className="w-3 h-3 mr-1" />
                                                    已完成
                                                </Badge>
                                            ) : doc.status === 'processing' || doc.status === 'pending' ? (
                                                <Badge variant="secondary">
                                                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                                    分析中
                                                </Badge>
                                            ) : (
                                                <Badge variant="destructive">
                                                    <AlertCircle className="w-3 h-3 mr-1" />
                                                    失败
                                                </Badge>
                                            )}
                                            {(doc.status === 'ready' || doc.status === 'success') && (
                                                <Eye className="w-4 h-4 text-muted-foreground" />
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                )}
            </Card>

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
                            <div className="flex items-center gap-2">
                                {selectedHistoryId && (
                                    <Button variant="outline" size="sm" onClick={handleResetToNew}>
                                        <RotateCcw className="w-3 h-3 mr-1" />
                                        新建分析
                                    </Button>
                                )}
                                <Button variant="outline" size="sm" onClick={handleExportPDF}>
                                    导出 PDF
                                </Button>
                            </div>
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
