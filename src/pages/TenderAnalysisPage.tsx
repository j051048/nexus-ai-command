import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ListChecks, Bot, Loader2, Upload, AlertCircle, CheckCircle2, FileText, ArrowRight, ChevronUp, ChevronDown, Clock, Eye, RotateCcw } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { getApiBaseUrl } from '@/lib/apiConfig';
import { toast } from "sonner";
import { httpClient } from '@/lib/httpClient';
import { useUser } from "@/contexts/UserContext";
import { AICopilotInsight } from '@/components/common/AICopilotInsight';
import { AIInsightPanel } from '@/components/ai/AIInsightPanel';

interface HistoryDoc {
    id: string;
    name: string;
    doc_type: string | null;
    status: string | null;
    extracted_data: Record<string, unknown>;
    owner_id: string | null;
    created_at: string;
    ownerName: string;
}

interface ExtractedData {
    full_analysis_markdown?: string;
    redlines?: string[];
    technical_deviations?: string[];
    tags?: string[];
    doc_type?: string;
    summary?: string;
}

interface TenderReportSection {
    id: string;
    title: string;
    content: string;
    defaultOpen?: boolean;
}

function stripMarkdownTitle(line: string) {
    return line.replace(/^#{1,6}\s*/, '').trim();
}

function buildTenderReportSections(report: string): TenderReportSection[] {
    const chunks = report
        .split(/\n(?=#{3,6}\s)/g)
        .map((chunk) => chunk.trim())
        .filter(Boolean);
    const sections = chunks.length > 1
        ? chunks.map((chunk, index) => {
            const [firstLine, ...rest] = chunk.split('\n');
            return {
                id: `section-${index}`,
                title: stripMarkdownTitle(firstLine || `段落 ${index + 1}`),
                content: rest.join('\n').trim() || chunk,
            };
        })
        : [{ id: 'full-report', title: '完整报告', content: report }];

    const classified: TenderReportSection[] = [
        {
            id: 'next-actions',
            title: '下一步行动',
            content: [
                '1. 先人工复核否决项和关键评分条款。',
                '2. 补齐技术偏离说明、证明材料和报价依据。',
                '3. 再让 AI 生成投标响应策略和材料清单。',
            ].join('\n'),
            defaultOpen: true,
        },
    ];

    const used = new Set<number>();
    const pick = (title: string, pattern: RegExp) => {
        const picked = sections
            .map((section, index) => ({ section, index }))
            .filter(({ section }) => pattern.test(section.title) || pattern.test(section.content));
        picked.forEach(({ index }) => used.add(index));
        classified.push({
            id: title,
            title,
            content: picked.map(({ section }) => `### ${section.title}\n${section.content}`).join('\n\n') || '暂无明显发现。',
            defaultOpen: false,
        });
    };

    pick('否决项', /否决|redline|废标|资格|必须|不得/i);
    pick('扣分风险', /扣分|偏离|deviation|风险|评分|响应/i);
    pick('需补材料', /材料|证明|附件|资质|补齐|证据|文件/i);

    const remaining = sections.filter((_, index) => !used.has(index));
    if (remaining.length > 0) {
        classified.push({
            id: 'evidence',
            title: '完整依据',
            content: remaining.map((section) => `### ${section.title}\n${section.content}`).join('\n\n'),
            defaultOpen: false,
        });
    }

    return classified;
}

function TenderReportSections({ report }: { report: string }) {
    const sections = buildTenderReportSections(report);

    return (
        <div className="space-y-2">
            {sections.map((section) => (
                <details
                    key={section.id}
                    open={section.defaultOpen}
                    className="rounded-lg border bg-background"
                >
                    <summary className="cursor-pointer list-none px-3 py-2 text-sm font-medium">
                        {section.title}
                    </summary>
                    <pre className="whitespace-pre-wrap border-t px-3 py-2 font-sans text-sm leading-relaxed text-foreground">
                        {section.content}
                    </pre>
                </details>
            ))}
        </div>
    );
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
    const [showHistory, setShowHistory] = useState(false);
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
            const response = await httpClient.get('/api/documents');
            const data = response.data?.documents || [];

            const bidDocs = (data || []).filter((doc: Record<string, unknown>) => {
                const ed = typeof doc.extracted_data === 'string'
                    ? JSON.parse(doc.extracted_data)
                    : doc.extracted_data;
                const dt = doc.doc_type || (ed && ed.doc_type);
                return dt === 'bid' || dt === 'tender';
            });

            const ownerIds = [...new Set(bidDocs.map((d: Record<string, unknown>) => d.owner_id).filter(Boolean))] as string[];
            let nameMap: Record<string, string> = {};

            if (ownerIds.length > 0) {
                const userResponse = await httpClient.get('/api/users/profile');
                const users = userResponse.data?.users || [];
                nameMap = Object.fromEntries(
                    (users || []).map((u: { id: string; name?: string }) => [u.id, u.name || '未知用户'])
                );
            }

            const withNames: HistoryDoc[] = bidDocs.map((d: Record<string, unknown>) => ({
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
            // Silently fail — empty history list is acceptable UX
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

        generateReport(histDoc.extracted_data as ExtractedData, histDoc.name);
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

            const endpoint = `${getApiBaseUrl()}/api/documents/upload`;

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

                    const ed = typeof existingDoc.extracted_data === 'string'
                        ? JSON.parse(existingDoc.extracted_data)
                        : (existingDoc.extracted_data || {});

                    if (existingDoc.status === 'ready' || existingDoc.status === 'success') {
                        setDocId(existingDocId);
                        setSelectedHistoryId(existingDocId);
                        generateReport(ed as ExtractedData, existingDoc.name);
                        setAnalyzing(false);
                        setProgress(100);
                        setCurrentStep(3);
                        fetchHistory();
                        toast.success(`已加载「${existingDoc.name}」的分析报告`);
                    } else if (existingDoc.status === 'processing' || existingDoc.status === 'pending') {
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
                // Polling error — continue polling, next attempt may succeed
            }

            if (doc) {
                const prog = (doc.progress as number) || 0;
                setProgress(prog);

                // Map Progress to Steps
                if (prog < 30) setCurrentStep(0);
                else if (prog < 60) setCurrentStep(1);
                else if (prog < 90) setCurrentStep(2);
                else setCurrentStep(3);

                if (doc.status === 'ready' || doc.status === 'success') {
                    generateReport(doc.extracted_data as ExtractedData);
                    setAnalyzing(false);
                    setSelectedHistoryId(docId);
                    toast.success("AI 诊断完成");
                    fetchHistory(); // Refresh history list
                    return; // stop polling
                } else if (doc.status === 'failed' || doc.status === 'error') {
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

    const generateReport = (data: ExtractedData, docName?: string) => {
        if (!data) return;

        // 优先使用后端生成的高质量 Markdown 报告
        if (data.full_analysis_markdown) {
            setReport(data.full_analysis_markdown);
            return;
        }

        const redlines = data.redlines?.map((r: string) => `- \u{1F6A8} ${r}`).join('\n') || "- 未发现明显否决性条款";
        const deviations = data.technical_deviations?.map((d: string) => `- \u26A0\uFE0F ${d}`).join('\n') || "- 未发现明显技术偏离";
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
            toast.error("PDF 生成失败");
        }
    };

    const latestReadyDoc = historyDocs.find((doc) => doc.status === 'ready' || doc.status === 'success');
    const nextActionTitle = analyzing
        ? 'AI 正在审阅标书'
        : report
            ? '下一步投标动作：复核报告'
            : latestReadyDoc
                ? `下一步投标动作：查看 ${latestReadyDoc.name}`
                : file
                    ? `下一步投标动作：诊断 ${file.name}`
                    : '下一步投标动作：上传招标文件';
    const nextActionHint = analyzing
        ? steps[currentStep] || '正在生成诊断报告'
        : report
            ? '先看否决项、技术偏离和评分风险，再决定是否进入方案撰写。'
            : latestReadyDoc
                ? '已有历史分析可复用，先打开最新报告，避免重复上传。'
                : file
                    ? '文件已就绪，开始 AI 诊断后会自动提取否决项和扣分项。'
                    : '支持 PDF / Word / DOCX。先上传文件，复杂报告和历史记录默认放在后面。';

    return (
        <div className="mx-auto max-w-5xl space-y-4 pb-20">
            <div className="flex flex-col gap-2">
                <h1 className="text-xl font-semibold">智能标书审阅</h1>
                <p className="text-muted-foreground">快速识别否决项、扣分项和下一步投标风险。</p>
            </div>

            <AIInsightPanel
                variant="compact"
                icon={ListChecks}
                title={nextActionTitle}
                summary={nextActionHint}
                trustLevel={report || latestReadyDoc ? 'high' : file ? 'medium' : 'low'}
                score={report || latestReadyDoc ? 88 : file ? 74 : 52}
                stats={[
                    { label: '历史', value: `${historyDocs.length} 份` },
                    { label: '状态', value: analyzing ? '诊断中' : report ? '已生成' : file ? '待诊断' : '待上传' },
                ]}
                actions={[
                    {
                        label: file && !report ? '开始诊断' : latestReadyDoc && !report ? '打开最新报告' : '查看记录',
                        variant: 'default',
                        disabled: analyzing || (!file && !latestReadyDoc && !report),
                        onClick: () => {
                            if (file && !report) {
                                handleStartAnalysis();
                                return;
                            }
                            if (latestReadyDoc && !report) {
                                handleLoadFromHistory(latestReadyDoc);
                                return;
                            }
                            setShowHistory(true);
                        },
                    },
                    {
                        label: '选择文件',
                        variant: 'outline',
                        onClick: () => document.getElementById('tender-input')?.click(),
                    },
                ]}
            />

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
                                context="基于 AI 全文扫描与条款比对"
                                insights={[]}
                                className="border-0 shadow-none bg-transparent p-0 mb-4"
                            />
                            <TenderReportSections report={report} />
                        </CardContent>
                    </Card>
                )}
            </div>
        </div>
    );
}
