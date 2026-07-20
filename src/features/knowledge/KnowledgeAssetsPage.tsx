import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BookOpenCheck,
  CheckCircle2,
  FileText,
  Library,
  Loader2,
  PanelsTopLeft,
  Search,
  SlidersHorizontal,
  ShieldCheck,
  Upload,
} from 'lucide-react';
import { toast } from 'sonner';

import { KnowledgeSubnav } from '@/components/knowledge/KnowledgeSubnav';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
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
  indexed_at?: string | null;
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

export default function KnowledgeAssetsPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<KnowledgeCategory>('all');
  const [uploadCategory, setUploadCategory] = useState<KnowledgeCategory>('product');
  const [visibility, setVisibility] = useState<Visibility>('organization');
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);

  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      const response = await httpClient.get('/api/documents', { silentError: true });
      const rows = response.data?.data?.documents ?? response.data?.documents ?? [];
      setDocuments((Array.isArray(rows) ? rows : []).map(normalizeDocument));
    } catch {
      toast.error('知识资产暂时无法加载，请稍后重试');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadDocuments();
  }, []);

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

  const indexedCount = documents.filter((document) =>
    ['ready', 'completed'].includes(document.status || ''),
  ).length;
  const verifiedCount = documents.filter((document) => document.review_status === 'verified').length;
  const staleCount = documents.filter((document) =>
    document.review_status === 'expired'
    || Boolean(document.valid_until && new Date(document.valid_until).getTime() < Date.now()),
  ).length;

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
      toast.success(reviewStatus === 'verified' ? '资料已标记为可信证据' : '资料已停止用于正式证据');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '资料审核状态更新失败');
    }
  };

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    try {
      const body = new FormData();
      body.append('files', file);
      body.append('category', uploadCategory === 'all' ? 'other' : uploadCategory);
      body.append('visibility', visibility);
      const response = await httpClient.post('/api/documents/upload', body, {
        headers: { 'Content-Type': 'multipart/form-data' },
        silentError: true,
      });
      const result = response.data?.data?.results?.[0];
      if (result?.status === 'error') throw new Error(result.reason || '文档解析失败');
      toast.success(result?.status === 'duplicate' ? '企业知识库中已有相同资料' : '资料已上传，正在建立 AI 索引');
      await loadDocuments();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '上传失败，请重试');
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  return (
    <main className="min-h-full bg-background">
      <header className="border-b bg-card px-6 py-5">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary">
              <Library className="h-4 w-4" />
              企业知识资产
            </div>
            <h1 className="text-2xl font-semibold">让每一份资料都能被 AI 找到并引用</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              统一存放产品、手册、法规、竞品和历史方案，作为方案生成与投标作战的可信证据源。
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <Button asChild variant="outline">
              <Link to="/growth/solutions">
                <PanelsTopLeft className="mr-2 h-4 w-4" />
                用资料生成方案
              </Link>
            </Button>
            <Button asChild variant="ghost">
              <Link to="/documents">
                <SlidersHorizontal className="mr-2 h-4 w-4" />
                批量管理
              </Link>
            </Button>
            <label className="space-y-1 text-xs text-muted-foreground">
              资料类型
              <select
                value={uploadCategory}
                onChange={(event) => setUploadCategory(event.target.value as KnowledgeCategory)}
                className="block h-9 rounded-md border bg-background px-3 text-sm text-foreground"
              >
                {KNOWLEDGE_CATEGORIES.filter((item) => item.value !== 'all').map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-xs text-muted-foreground">
              可见范围
              <select
                value={visibility}
                onChange={(event) => setVisibility(event.target.value as Visibility)}
                className="block h-9 rounded-md border bg-background px-3 text-sm text-foreground"
              >
                <option value="organization">全企业</option>
                <option value="department">本部门</option>
                <option value="private">仅自己</option>
              </select>
            </label>
            <input ref={inputRef} type="file" className="hidden" accept=".pdf,.docx,.txt,.md" onChange={handleUpload} />
            <Button onClick={() => inputRef.current?.click()} disabled={isUploading}>
              {isUploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
              上传资料
            </Button>
          </div>
        </div>
      </header>

      <KnowledgeSubnav />

      <div className="mx-auto max-w-7xl px-6 py-5">
        <section className="grid border-y sm:grid-cols-4">
          <div className="py-4 sm:border-r sm:px-4 sm:first:pl-0">
            <div className="text-2xl font-semibold">{documents.length}</div>
            <div className="mt-1 text-xs text-muted-foreground">企业资料</div>
          </div>
          <div className="py-4 sm:border-r sm:px-4">
            <div className="text-2xl font-semibold">{indexedCount}</div>
            <div className="mt-1 text-xs text-muted-foreground">可被 AI 检索</div>
          </div>
          <div className="py-4 sm:border-r sm:px-4">
            <div className="text-2xl font-semibold">{new Set(documents.map((item) => item.doc_type || item.category)).size}</div>
            <div className="mt-1 text-xs text-muted-foreground">知识分类</div>
          </div>
          <div className="py-4 sm:px-4">
            <div className="text-2xl font-semibold">{verifiedCount}<span className="ml-2 text-sm font-normal text-amber-700">{staleCount ? `${staleCount} 过期` : ''}</span></div>
            <div className="mt-1 text-xs text-muted-foreground">已审核可信资料</div>
          </div>
        </section>

        <section className="mt-5 flex flex-col gap-3 border-b pb-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full lg:max-w-md">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索产品型号、应用行业、竞品或方案关键词"
              className="h-9 w-full rounded-md border bg-card pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="flex flex-wrap gap-1">
            {KNOWLEDGE_CATEGORIES.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setFilter(item.value)}
                className={cn(
                  'rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
                  filter === item.value && 'bg-foreground text-background hover:bg-foreground hover:text-background',
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </section>

        <section className="divide-y">
          {isLoading && (
            <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />正在加载企业资料
            </div>
          )}
          {!isLoading && filtered.length === 0 && (
            <div className="flex flex-col items-center py-20 text-center">
              <BookOpenCheck className="h-9 w-9 text-muted-foreground/40" />
              <h2 className="mt-3 font-medium">还没有匹配的知识资产</h2>
              <p className="mt-1 text-sm text-muted-foreground">上传第一份产品资料或历史方案，AI 才能基于企业事实生成内容。</p>
            </div>
          )}
          {filtered.map((document) => {
            const type = document.doc_type || document.category || 'other';
            const extracted = typeof document.extracted_data === 'object' ? document.extracted_data : {};
            const isReady = ['ready', 'completed'].includes(document.status || '');
            return (
              <article key={document.id} className="grid gap-3 py-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                <div className="flex min-w-0 gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-card">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="truncate text-sm font-medium">{document.name}</h2>
                      <Badge variant="outline">{categoryLabel(type)}</Badge>
                      {isReady ? (
                        <span className="flex items-center gap-1 text-xs text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />索引就绪</span>
                      ) : (
                        <span className="text-xs text-amber-700">处理中</span>
                      )}
                      <Badge variant={document.review_status === 'verified' ? 'default' : 'secondary'}>{document.review_status === 'verified' ? '可信证据' : document.review_status === 'expired' ? '已过期' : '待审核'}</Badge>
                    </div>
                    <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
                      {extracted?.summary || '等待 AI 提取摘要与可引用证据'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  {document.source_version && <span>v{document.source_version}</span>}
                  {document.valid_until && <time>有效至 {new Date(document.valid_until).toLocaleDateString('zh-CN')}</time>}
                  <span className="flex items-center gap-1"><ShieldCheck className="h-3.5 w-3.5" />{visibilityLabel(document.visibility)}</span>
                  {document.created_at && <time>{new Date(document.created_at).toLocaleDateString('zh-CN')}</time>}
                  {document.review_status !== 'verified' && isReady && <Button variant="ghost" size="sm" onClick={() => reviewDocument(document, 'verified')}>设为可信</Button>}
                  {document.review_status === 'verified' && <Button variant="ghost" size="sm" onClick={() => reviewDocument(document, 'expired')}>停用证据</Button>}
                </div>
              </article>
            );
          })}
        </section>
      </div>
    </main>
  );
}
