import { useEffect, useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { downloadBlob } from '@/features/deliverables/exportContent';
import { httpClient } from '@/lib/httpClient';

interface DocumentPreview {
  id: string; name: string; content: string; summary: string; truncated: boolean;
  facts: Record<string, string>;
  citations: { id: string; index: number; excerpt: string }[];
  review_status?: string; source_version?: string; valid_until?: string; quality_score?: number;
  has_original: boolean;
}

export function KnowledgeDocumentDrawer({ documentId, onClose }: { documentId: string | null; onClose: () => void }) {
  const [data, setData] = useState<DocumentPreview | null>(null);
  const [error, setError] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    setData(null); setError(false);
    if (!documentId) return;
    const controller = new AbortController();
    void httpClient.get(`/api/documents/${documentId}/preview`, { signal: controller.signal, silentError: true })
      .then(response => { if (!controller.signal.aborted) setData(response.data.data); })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [documentId, reload]);
  const download = async () => {
    if (!data || downloading) return;
    setDownloading(true);
    try {
      const response = await httpClient.get(`/api/documents/${data.id}/source`, { responseType: 'blob', silentError: true });
      downloadBlob(response.data, data.name);
    } catch { toast.error('原文件暂时无法下载，请重试'); }
    finally { setDownloading(false); }
  };
  return <Sheet open={Boolean(documentId)} onOpenChange={open => { if (!open) onClose(); }}>
    <SheetContent className="flex w-full flex-col sm:max-w-2xl">
      <SheetHeader className="pr-6"><SheetTitle className="break-words">{data?.name || '资料预览'}</SheetTitle><SheetDescription>{data?.source_version ? `版本 ${data.source_version}` : '企业资料'}</SheetDescription></SheetHeader>
      {error ? <div role="alert" className="space-y-3 py-6"><p>资料暂不可用或访问权限已变更。</p><Button variant="outline" onClick={() => setReload(value => value + 1)}>重试</Button></div> : !data ? <Loader2 className="h-5 w-5 animate-spin" aria-label="加载资料" /> : <>
        <div className="flex flex-wrap gap-3 border-b pb-3 text-xs text-muted-foreground"><span>{data.review_status === 'verified' ? '人工已核验' : '尚未人工核验'}</span><span>质量检测 {data.quality_score == null ? '未评估' : `${Math.round(data.quality_score * 100)}分`}</span><span>{data.valid_until ? `有效至 ${new Date(data.valid_until).toLocaleDateString('zh-CN')}` : '未设置有效期'}</span></div>
        <Tabs defaultValue="content" className="flex min-h-0 flex-1 flex-col"><TabsList className="justify-start"><TabsTrigger value="content">正文</TabsTrigger><TabsTrigger value="facts">提取事实</TabsTrigger><TabsTrigger value="citations">引用片段</TabsTrigger></TabsList>
          <div className="min-h-0 flex-1 overflow-y-auto py-3 text-sm leading-7">
            <TabsContent value="content"><p className="whitespace-pre-wrap break-words">{data.content || '尚无解析正文，原文件仍可单独查看。'}</p>{data.truncated && <p className="mt-4 text-xs text-muted-foreground">当前为部分内容，完整资料请下载原文件。</p>}</TabsContent>
            <TabsContent value="facts"><p className="mb-4 whitespace-pre-wrap">{data.summary || '尚未提取摘要'}</p><dl className="divide-y">{Object.entries(data.facts).map(([key, value]) => <div key={key} className="py-3"><dt className="font-medium">{key}</dt><dd className="whitespace-pre-wrap break-words text-muted-foreground">{value}</dd></div>)}</dl></TabsContent>
            <TabsContent value="citations"><ol className="divide-y">{data.citations.map(citation => <li key={citation.id} className="py-3"><p className="text-xs text-muted-foreground">片段 {citation.index + 1}</p><p className="whitespace-pre-wrap break-words">{citation.excerpt}</p></li>)}</ol>{!data.citations.length && <p>尚无可引用片段</p>}</TabsContent>
          </div>
        </Tabs>
        <div className="border-t pt-3"><Button variant="outline" disabled={!data.has_original || downloading} onClick={() => void download()}><Download className="mr-2 h-4 w-4" />{downloading ? '下载中' : '下载原文件'}</Button></div>
      </>}
    </SheetContent>
  </Sheet>;
}
