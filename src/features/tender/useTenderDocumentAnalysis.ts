import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ChangeEvent } from 'react';

import { getApiBaseUrl } from '@/lib/apiConfig';
import { httpClient } from '@/lib/httpClient';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';

interface HistoryDoc {
  id: string;
  name: string;
  doc_type: string | null;
  status: string | null;
  extracted_data: ExtractedData;
  created_at: string;
}

interface ExtractedData {
  full_analysis_markdown?: string;
  redlines?: string[];
  technical_deviations?: string[];
  tags?: string[];
  doc_type?: string;
  summary?: string;
}

function parseExtractedData(value: unknown): ExtractedData {
  if (!value) return {};
  if (typeof value === 'string') {
    try {
      return JSON.parse(value) as ExtractedData;
    } catch {
      return {};
    }
  }
  return value as ExtractedData;
}

function reportFromExtractedData(data: ExtractedData, documentName: string) {
  if (data.full_analysis_markdown) return data.full_analysis_markdown;
  const redlines = data.redlines?.map((item) => `- ${item}`).join('\n') || '- 未发现明确否决性条款，仍需人工复核';
  const deviations = data.technical_deviations?.map((item) => `- ${item}`).join('\n') || '- 未发现明确技术偏离，仍需逐项核验';
  return [
    `### 标书分析报告 - ${documentName}`,
    '',
    `**文档类型**：${data.doc_type || '待确认'}`,
    `**摘要**：${data.summary || '暂无摘要'}`,
    `**标签**：${data.tags?.join('、') || '暂无标签'}`,
    '',
    '#### 否决性条款',
    redlines,
    '',
    '#### 技术偏离建议',
    deviations,
    '',
    '> 本报告由 AI 生成，仅供初审，最终结论以人工复核为准。',
  ].join('\n');
}

export const TENDER_ANALYSIS_STEPS = [
  '建立文档索引',
  '提取否决性条款',
  '比对评分与技术偏离',
  '整理风险和证据',
];

export function useTenderDocumentAnalysis(userId?: string) {
  const [file, setFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [report, setReport] = useState<string | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [analysisStartTime, setAnalysisStartTime] = useState(0);
  const [historyDocs, setHistoryDocs] = useState<HistoryDoc[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const response = await httpClient.get('/api/documents', { silentError: true });
      const documents = response.data?.documents || response.data?.data?.documents || [];
      const history = (documents as Array<Record<string, unknown>>)
        .filter((document) => {
          const extracted = parseExtractedData(document.extracted_data);
          const type = document.doc_type || extracted.doc_type;
          return type === 'bid' || type === 'tender';
        })
        .map((document) => ({
          id: String(document.id),
          name: String(document.name || '未命名招标文件'),
          doc_type: document.doc_type ? String(document.doc_type) : null,
          status: document.status ? String(document.status) : null,
          extracted_data: parseExtractedData(document.extracted_data),
          created_at: String(document.created_at || new Date().toISOString()),
        }));
      setHistoryDocs(history);
    } catch {
      setHistoryDocs([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchHistory();
  }, [fetchHistory]);

  const loadHistoryDocument = useCallback((document: HistoryDoc) => {
    if (document.status === 'processing' || document.status === 'pending') {
      setDocId(document.id);
      setAnalyzing(true);
      setAnalysisStartTime(Date.now());
      setFile(null);
      setSelectedHistoryId(document.id);
      toast.info('该文件仍在分析中，正在同步进度');
      return;
    }
    if (document.status === 'failed' || document.status === 'error') {
      toast.error('该文件分析失败，请重新上传');
      return;
    }
    setSelectedHistoryId(document.id);
    setDocId(document.id);
    setFile(null);
    setAnalyzing(false);
    setProgress(100);
    setCurrentStep(3);
    setReport(reportFromExtractedData(document.extracted_data, document.name));
  }, []);

  const reset = useCallback(() => {
    setReport(null);
    setDocId(null);
    setSelectedHistoryId(null);
    setFile(null);
    setProgress(0);
    setCurrentStep(0);
    setAnalyzing(false);
  }, []);

  const onFileChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0];
    if (!selected) return;
    setFile(selected);
    setReport(null);
    setCurrentStep(0);
    setDocId(null);
    setProgress(0);
    setSelectedHistoryId(null);
  }, []);

  const loadDocumentById = useCallback(async (documentId: string) => {
    const { data, error } = await supabase
      .from('documents')
      .select('id, name, status, extracted_data')
      .eq('id', documentId)
      .single();
    if (error || !data) throw new Error('加载已有文件失败，请刷新后重试');
    const extracted = parseExtractedData(data.extracted_data);
    setDocId(documentId);
    setSelectedHistoryId(documentId);
    if (data.status === 'ready' || data.status === 'success') {
      setReport(reportFromExtractedData(extracted, data.name));
      setAnalyzing(false);
      setProgress(100);
      setCurrentStep(3);
    } else if (data.status === 'processing' || data.status === 'pending') {
      setAnalyzing(true);
      setAnalysisStartTime(Date.now());
    } else {
      throw new Error('该文件之前的分析未成功，请重新上传');
    }
  }, []);

  const startAnalysis = useCallback(async () => {
    if (!file) return;
    setAnalyzing(true);
    setCurrentStep(0);
    setProgress(0);
    setReport(null);
    setSelectedHistoryId(null);
    setAnalysisStartTime(Date.now());

    try {
      const formData = new FormData();
      formData.append('files', file);
      if (userId) formData.append('userId', userId);
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) throw new Error('请先登录');
      const endpoint = `${getApiBaseUrl()}/api/documents/upload`;
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { Authorization: `Bearer ${session.access_token}` },
        body: formData,
        mode: 'cors',
      }).catch(() => {
        throw new Error('无法连接文档服务，请稍后重试');
      });
      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(errorBody.message || errorBody.reason || `上传失败 (HTTP ${response.status})`);
      }
      const payload = await response.json();
      const firstResult = (payload.data?.results || payload.results)?.[0];
      if (firstResult?.status === 'error') throw new Error(firstResult.reason || '文档解析失败');
      if (firstResult?.status === 'duplicate' && firstResult.existing_document_id) {
        toast.info('检测到相同文件，已加载已有分析');
        await loadDocumentById(firstResult.existing_document_id);
        return;
      }
      if (!firstResult?.document_id) throw new Error('上传返回异常，未获取文档 ID');
      setDocId(firstResult.document_id);
      toast.info('文件已上传，AI 开始审阅');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '上传处理失败，请重试');
      setAnalyzing(false);
    }
  }, [file, loadDocumentById, userId]);

  useEffect(() => {
    if (!docId || !analyzing) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let delay = 2_000;

    const poll = async () => {
      if (cancelled) return;
      const { data } = await supabase
        .from('documents')
        .select('name, status, progress, extracted_data')
        .eq('id', docId)
        .single();
      if (cancelled) return;
      if (data) {
        const nextProgress = Number(data.progress || 0);
        setProgress(nextProgress);
        setCurrentStep(nextProgress < 30 ? 0 : nextProgress < 60 ? 1 : nextProgress < 90 ? 2 : 3);
        if (data.status === 'ready' || data.status === 'success') {
          setReport(reportFromExtractedData(parseExtractedData(data.extracted_data), data.name || file?.name || '招标文件'));
          setAnalyzing(false);
          setSelectedHistoryId(docId);
          setProgress(100);
          void fetchHistory();
          toast.success('标书风险审阅完成');
          return;
        }
        if (data.status === 'failed' || data.status === 'error') {
          setAnalyzing(false);
          void fetchHistory();
          toast.error('标书审阅失败，请重新上传');
          return;
        }
      }
      if (Date.now() - analysisStartTime > 180_000) {
        setAnalyzing(false);
        toast.error('标书审阅超时，请稍后从历史记录继续查看');
        return;
      }
      delay = Math.min(delay * 2, 8_000);
      timer = setTimeout(poll, delay);
    };
    timer = setTimeout(poll, delay);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [analysisStartTime, analyzing, docId, fetchHistory, file?.name]);

  const currentDocumentName = useMemo(() =>
    historyDocs.find((document) => document.id === selectedHistoryId)?.name || file?.name || '标书分析报告',
  [file?.name, historyDocs, selectedHistoryId]);

  const exportPDF = useCallback(async () => {
    const element = document.getElementById('analysis-report-content');
    if (!element || !report) return;
    try {
      toast.info('正在生成 PDF');
      const html2canvas = (await import('html2canvas')).default;
      const { jsPDF } = await import('jspdf');
      const canvas = await html2canvas(element, { scale: 2, useCORS: true, logging: false, backgroundColor: '#ffffff' });
      const pdf = new jsPDF('p', 'mm', 'a4');
      const margin = 10;
      const contentWidth = pdf.internal.pageSize.getWidth() - margin * 2;
      const contentHeight = (canvas.height * contentWidth) / canvas.width;
      const pageHeight = pdf.internal.pageSize.getHeight() - margin * 2;
      const image = canvas.toDataURL('image/png');
      let offset = 0;
      pdf.addImage(image, 'PNG', margin, margin, contentWidth, contentHeight);
      while (contentHeight - offset > pageHeight) {
        offset += pageHeight;
        pdf.addPage();
        pdf.addImage(image, 'PNG', margin, margin - offset, contentWidth, contentHeight);
      }
      pdf.save(`${currentDocumentName}_审阅报告.pdf`);
      toast.success('审阅报告已下载');
    } catch {
      toast.error('PDF 生成失败');
    }
  }, [currentDocumentName, report]);

  return {
    file,
    analyzing,
    currentStep,
    report,
    docId,
    progress,
    historyDocs,
    historyLoading,
    selectedHistoryId,
    currentDocumentName,
    onFileChange,
    startAnalysis,
    loadHistoryDocument,
    reset,
    exportPDF,
  };
}
