import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  BookOpenCheck,
  CheckCircle2,
  FileText,
  FolderUp,
  Library,
  Loader2,
  PanelsTopLeft,
  Search,
  RotateCcw,
  Settings2,
  ShieldCheck,
  FileSearch,
  Upload,
} from 'lucide-react';
import { toast } from 'sonner';

import { KnowledgeSubnav } from '@/components/knowledge/KnowledgeSubnav';
import { LoadingState } from '@/components/common/LoadingState';
import { OperationalMetricStrip } from '@/components/common/OperationalMetricStrip';
import { PrecisionPageHeader } from '@/components/common/PrecisionPageHeader';
import { WorkEmptyState, WorkErrorState } from '@/components/common/WorkState';
import { dispatchAIChatMessage } from '@/components/layout/GlobalCommandBar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useActivationState } from '@/hooks/useActivationState';
import { httpClient } from '@/lib/httpClient';
import { cn } from '@/lib/utils';

const KNOWLEDGE_CATEGORIES = [
  { value: 'all', label: '全部资料' },
  { value: 'product', label: '产品资料' },
  { value: 'manual', label: '仪器手册' },
  { value: 'regulation', label: '法规与标准' },
  { value: 'competitor', label: '竞品资料' },
  { value: 'case', label: '客户案例' },
  { value: 'proposal', label: '历史方案' },
  { value: 'tender', label: '招标文件' },
  { value: 'training', label: '培训资料' },
  { value: 'other', label: '其他' },
] as const;

type KnowledgeCategory = (typeof KNOWLEDGE_CATEGORIES)[number]['value'];
type UploadCategory = Exclude<KnowledgeCategory, 'all'> | 'auto';
type Visibility = 'organization' | 'department' | 'private';

interface KnowledgeDocument {
  id: string;
  name: string;
  doc_type?: string;
  category?: string;
  visibility?: Visibility;
  status?: string;
  created_at?: string;
  extracted_data?: { summary?: string; tags?: string[] } | string;
  review_status?: 'pending' | 'verified' | 'rejected' | 'expired';
  source_version?: string | null;
  valid_until?: string | null;
  quality_score?: number | null;
  progress?: number;
  stage?: string;
  error_log?: string | null;
  ingestion_attempt?: number;
  ingestion_updated_at?: string | null;
  ingestion_error_code?: string | null;
  source_storage_path?: string | null;
}

interface KnowledgeReadiness {
  score: number;
  ready: boolean;
  next_actions: string[];
  required_categories: Array<{ key: string; label: string; covered: boolean }>;
}

function normalizeDocument(row: KnowledgeDocument): KnowledgeDocument {
  let extracted = row.extracted_data;
  if (typeof extracted === 'string') {
    try {
      extracted = JSON.parse(extracted) as KnowledgeDocument['extracted_data'];
    } catch {
      extracted = {};
    }
  }
  return { ...row, extracted_data: extracted };
}

function categoryLabel(value?: string) {
  return KNOWLEDGE_CATEGORIES.find((item) => item.value === value)?.label ?? '其他';
}

function visibilityLabel(value?: Visibility) {
  if (value === 'private') return '仅自己';
  if (value === 'department') return '本部门';
  return '全企业';
}

const INGESTION_STAGE_LABELS: Record<string, string> = {
  uploading: '保存原文件',
  queued: '等待整理',
  parsing: '解析内容',
  analyzing: '提取事实',
  embedding: '建立索引',
  completed: '可供 AI 引用',
  failed: '整理失败',
};

function ingestionStageLabel(document: KnowledgeDocument) {
  if (['ready', 'completed'].includes(document.status || '')) return '可供 AI 引用';
  return INGESTION_STAGE_LABELS[document.stage || ''] || '等待整理';
}

export default function KnowledgeAssetsPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const { state: activationState, update: updateActivation } = useActivationState();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<KnowledgeCategory>('all');
  const [uploadCategory, setUploadCategory] = useState<UploadCategory>('auto');
  const [visibility, setVisibility] = useState<Visibility>('organization');
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [readiness, setReadiness] = useState<KnowledgeReadiness | null>(null);
  const [loadError, setLoadError] = useState(false);

  const loadDocuments = useCallback(async (silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      const response = await httpClient.get('/api/documents', { silentError: true });
      const rows = response.data?.data?.documents ?? response.data?.documents ?? [];
      setDocuments((Array.isArray(rows) ? rows : []).map(normalizeDocument));
      if (!silent) setLoadError(false);
      try {
        const readinessResponse = await httpClient.get('/api/knowledge/readiness', {
          params: { artifact_type: 'customer_solution' },
          silentError: true,
        });
        const outer = readinessResponse.data?.data;
        setReadiness((outer?.data ?? outer ?? null) as KnowledgeReadiness | null);
      } catch {
        setReadiness(null);
      }
    } catch {
      if (!silent) {
        setLoadError(true);
        toast.error('企业资料暂时无法加载，请稍后重试');
      }
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const hasActiveIngestion = documents.some((document) =>
    ['pending', 'processing'].includes(document.status || ''),
  );

  useEffect(() => {
    if (!hasActiveIngestion) return undefined;
    const timer = window.setInterval(() => void loadDocuments(true), 2500);
    return () => window.clearInterval(timer);
  }, [hasActiveIngestion, loadDocuments]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return documents.filter((document) => {
      const type = document.doc_type || document.category || 'other';
      const extracted = typeof document.extracted_data === 'object' ? document.extracted_data : {};
      const haystack = [document.name, extracted?.summary, ...(extracted?.tags ?? [])]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return (filter === 'all' || type === filter) && (!needle || haystack.includes(needle));
    });
  }, [documents, filter, query]);

  const indexedCount = documents.filter((document) => ['ready', 'completed'].includes(document.status || '')).length;
  const verifiedCount = documents.filter((document) => document.review_status === 'verified').length;
  const staleCount = documents.filter((document) => document.review_status === 'expired' || Boolean(document.valid_until && new Date(document.valid_until).getTime() < Date.now())).length;

  const openAssistant = (prompt: string) => {
    window.dispatchEvent(new CustomEvent('proactive-chat'));
    dispatchAIChatMessage(prompt);
  };

  const reviewDocument = async (document: KnowledgeDocument, reviewStatus: 'verified' | 'expired') => {
    try {
      const response = await httpClient.patch(`/api/documents/${document.id}/review`, {
        review_status: reviewStatus,
        source_version: document.source_version || 'current',
        valid_until: document.valid_until || null,
        quality_score: reviewStatus === 'verified' ? (document.quality_score ?? 1) : document.quality_score,
      }, { silentError: true });
      const updated = response.data?.data;
      setDocuments((current) => current.map((item) => item.id === document.id ? normalizeDocument({ ...item, ...updated }) : item));
      toast.success(reviewStatus === 'verified' ? '资料已设为可信证据' : '资料已停止用于正式证据');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '资料状态更新失败');
    }
  };

  const retryIngestion = async (document: KnowledgeDocument) => {
    try {
      await httpClient.post(`/api/documents/${document.id}/retry`, undefined, {
        silentError: true,
      });
      setDocuments((current) => current.map((item) => (
        item.id === document.id
          ? { ...item, status: 'pending', stage: 'queued', progress: 0, error_log: null }
          : item
      )));
      toast.success('资料已重新提交整理');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '资料重试失败');
    }
  };

  const uploadFiles = async (files: File[]) => {
    if (!files.length) return;
    if (files.length > 20) {
      toast.error('单次最多上传 20 份资料');
      return;
    }
    setIsUploading(true);
    try {
      const body = new FormData();
      files.forEach((file) => body.append('files', file));
      body.append('category', uploadCategory);
      body.append('visibility', visibility);
      const response = await httpClient.post('/api/documents/upload', body, {
        headers: { 'Content-Type': 'multipart/form-data' },
        silentError: true,
      });
      const results = response.data?.data?.results ?? [];
      const accepted = Array.isArray(results) ? results.filter((item: { status?: string }) => item.status !== 'error') : [];
      const failed = Array.isArray(results) ? results.filter((item: { status?: string }) => item.status === 'error') : [];
      if (!accepted.length && failed.length) throw new Error('资料未能上传，请检查文件格式');
      updateActivation({
        uploadedDocumentCount: Math.max(activationState.uploadedDocumentCount, documents.length) + accepted.length,
        uploadedFileNames: [...new Set([...activationState.uploadedFileNames, ...files.map((file) => file.name)])],
      });
      toast.success(`${accepted.length} 份资料已接收，AI 正在整理`);
      if (failed.length) toast.warning(`${failed.length} 份资料需要重新检查`);
      await loadDocuments();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '上传失败，请重试');
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  return (
    <main
      className={cn('min-h-full bg-background', isDragging && 'ring-2 ring-inset ring-primary/40')}
      onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={(event) => { if (event.currentTarget === event.target) setIsDragging(false); }}
      onDrop={(event) => {
        event.preventDefault();
        setIsDragging(false);
        void uploadFiles(Array.from(event.dataTransfer.files));
      }}
    >
      <div className="border-b bg-card px-6 py-5">
        <div className="mx-auto max-w-7xl">
          <PrecisionPageHeader
            className="border-b-0 pb-0"
            eyebrow="企业资料"
            title="AI 的企业事实库"
            description="上传一次，方案、投标和客户助手都能引用；正式外发内容优先采用已核验资料。"
            icon={Library}
            status={{
              label: indexedCount > 0 ? '检索可用' : '等待资料',
              detail: indexedCount > 0 ? `${indexedCount} 份已建立索引` : '上传资料后自动整理',
              tone: indexedCount > 0 ? 'success' : 'neutral',
            }}
            actions={<>
              <Button asChild variant="outline"><Link to="/growth/solutions"><PanelsTopLeft className="mr-2 h-4 w-4" />生成客户方案</Link></Button>
              <input ref={inputRef} type="file" multiple className="hidden" accept=".pdf,.docx,.pptx,.xlsx,.txt,.md,.csv" onChange={(event) => event.target.files && void uploadFiles(Array.from(event.target.files))} />
              <Button onClick={() => inputRef.current?.click()} disabled={isUploading}>{isUploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}上传资料</Button>
            </>}
          />
        </div>
      </div>

      <KnowledgeSubnav />

      <div className="mx-auto max-w-7xl px-6 py-5">
        <section className="relative">
          <OperationalMetricStrip
            ariaLabel="企业资料状态"
            metrics={[
              { label: '全部资料', value: documents.length, detail: '企业事实资产', icon: <FileText /> },
              { label: '可供检索', value: indexedCount, detail: '已完成内容索引', tone: indexedCount > 0 ? 'success' : 'default', icon: <Search /> },
              { label: '可信证据', value: verifiedCount, detail: staleCount > 0 ? `${staleCount} 份待更新` : '人工确认后可外发', tone: staleCount > 0 ? 'warning' : 'default', icon: <ShieldCheck /> },
              { label: '方案就绪度', value: readiness ? `${Math.round(readiness.score)}%` : '—', detail: readiness?.ready ? '可开始正式生成' : '继续补齐关键资料', tone: readiness?.ready ? 'success' : 'warning', icon: <CheckCircle2 /> },
            ]}
          />
          <details className="relative mt-2 flex justify-end">
            <summary className="flex cursor-pointer list-none items-center gap-2 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"><Settings2 className="h-3.5 w-3.5" />上传设置</summary>
            <div className="absolute right-0 top-8 z-20 grid w-64 gap-3 rounded-md border bg-popover p-4 shadow-lg">
              <label className="text-xs text-muted-foreground">资料类型<select value={uploadCategory} onChange={(event) => setUploadCategory(event.target.value as UploadCategory)} className="mt-1.5 h-9 w-full rounded-md border bg-background px-2 text-sm text-foreground"><option value="auto">AI 自动分类</option>{KNOWLEDGE_CATEGORIES.filter((item) => item.value !== 'all').map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
              <label className="text-xs text-muted-foreground">可见范围<select value={visibility} onChange={(event) => setVisibility(event.target.value as Visibility)} className="mt-1.5 h-9 w-full rounded-md border bg-background px-2 text-sm text-foreground"><option value="organization">全企业</option><option value="department">本部门</option><option value="private">仅自己</option></select></label>
            </div>
          </details>
        </section>

        {readiness && !readiness.ready && readiness.next_actions.length > 0 && (
          <section className="flex flex-wrap items-center gap-2 border-b py-3 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">下一步</span>
            {readiness.next_actions.slice(0, 3).map((action) => (
              <span key={action} className="rounded-sm bg-muted px-2 py-1">{action}</span>
            ))}
          </section>
        )}

        <section className="mt-5 flex flex-col gap-3 border-b pb-4 lg:flex-row lg:items-center">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索型号、行业、竞品或方案" className="h-9 w-full rounded-md border bg-card pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </div>
          <select aria-label="筛选资料类型" value={filter} onChange={(event) => setFilter(event.target.value as KnowledgeCategory)} className="h-9 rounded-md border bg-background px-3 text-sm text-foreground">{KNOWLEDGE_CATEGORIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
          <Button variant="ghost" size="sm" onClick={() => openAssistant('请检查当前企业资料库的缺口。按产品资料、仪器手册、应用案例、竞品、法规和历史方案六类，只告诉我最值得补充的三项。')}><FileSearch className="mr-2 h-4 w-4" />让 AI 检查缺口</Button>
        </section>

        <section className="divide-y">
          {isLoading && <LoadingState rows={5} message="正在加载企业资料" className="py-2" />}
          {!isLoading && loadError && (
            <WorkErrorState
              title="企业资料暂时无法加载"
              description="资料没有丢失。请检查网络或服务状态后重新加载。"
              onAction={() => void loadDocuments()}
            />
          )}
          {!isLoading && !loadError && filtered.length === 0 && (
            <WorkEmptyState
              icon={<BookOpenCheck className="h-5 w-5" />}
              title={documents.length ? '没有匹配的资料' : '从第一批企业资料开始'}
              description={documents.length
                ? '调整关键词或资料类型，AI 仍会保留现有索引。'
                : '上传公司介绍、产品彩页、仪器手册和应用案例，AI 会自动完成分类、索引与证据整理。'}
              actionLabel={documents.length ? undefined : '选择资料'}
              onAction={documents.length ? undefined : () => inputRef.current?.click()}
            />
          )}
          {!loadError && filtered.map((document) => {
            const type = document.doc_type || document.category || 'other';
            const extracted = typeof document.extracted_data === 'object' ? document.extracted_data : {};
            const isReady = ['ready', 'completed'].includes(document.status || '');
            const isFailed = ['error', 'failed'].includes(document.status || '');
            const progress = Math.max(0, Math.min(100, Number(document.progress || 0)));
            return (
              <article key={document.id} className="grid gap-3 py-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                <div className="flex min-w-0 gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-card"><FileText className="h-4 w-4 text-muted-foreground" /></div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2"><h2 className="truncate text-sm font-medium">{document.name}</h2><Badge variant="outline">{categoryLabel(type)}</Badge>{isReady ? <span className="flex items-center gap-1 text-xs text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />可检索</span> : isFailed ? <span className="flex items-center gap-1 text-xs text-destructive"><AlertCircle className="h-3.5 w-3.5" />整理失败</span> : <span className="text-xs text-amber-700">{ingestionStageLabel(document)} {progress}%</span>}{document.review_status === 'verified' && <Badge>可信</Badge>}</div>
                    <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">{extracted?.summary || '等待 AI 提取摘要与可引用证据'}</p>
                    {!isReady && !isFailed && <div className="mt-2 h-1 max-w-md overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary transition-[width] duration-300" style={{ width: `${Math.max(4, progress)}%` }} /></div>}
                    {isFailed && <p className="mt-1 text-xs text-muted-foreground">原文件已保留，可直接重新整理，无需再次上传。</p>}
                  </div>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1"><ShieldCheck className="h-3.5 w-3.5" />{visibilityLabel(document.visibility)}</span>
                  {document.created_at && <time>{new Date(document.created_at).toLocaleDateString('zh-CN')}</time>}
                  {document.review_status !== 'verified' && isReady && <Button variant="ghost" size="sm" onClick={() => reviewDocument(document, 'verified')}>设为可信</Button>}
                  {document.review_status === 'verified' && <Button variant="ghost" size="sm" onClick={() => reviewDocument(document, 'expired')}>停用</Button>}
                  {isFailed && <Button variant="outline" size="sm" onClick={() => retryIngestion(document)}><RotateCcw className="mr-1.5 h-3.5 w-3.5" />重试</Button>}
                </div>
              </article>
            );
          })}
        </section>
      </div>

      {isDragging && <div className="pointer-events-none fixed inset-6 z-50 flex items-center justify-center rounded-lg border-2 border-dashed border-primary bg-background/90 text-sm font-medium"><FolderUp className="mr-2 h-5 w-5 text-primary" />松开即可上传并自动分类</div>}
    </main>
  );
}
