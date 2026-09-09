import { useEffect, useRef, useState } from 'react';
import { Download, Eye, Loader2, RotateCcw, Send } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { downloadArtifact, getArtifactPreview, reviseArtifact, type ArtifactPreview, type ArtifactOutputFormat } from '@/features/deliverables/artifactApi';

export function ArtifactPreviewButton({ artifactId, onQueued }: { artifactId: string; onQueued?: () => void }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<ArtifactPreview | null>(null);
  const [previous, setPrevious] = useState<ArtifactPreview | null>(null);
  const [comparisonFailed, setComparisonFailed] = useState(false);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);
  const [format, setFormat] = useState<ArtifactOutputFormat>('docx');
  const [instructions, setInstructions] = useState('');
  const [busy, setBusy] = useState(false);
  const request = useRef({ text: '', key: '' });
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  useEffect(() => {
    if (!open) return;
    let disposed = false;
    setData(null); setPrevious(null); setError(false); setComparisonFailed(false);
    void getArtifactPreview(artifactId).then(async (result) => {
      if (disposed) return;
      setData(result); setFormat(result.requested_formats[0] || 'docx');
      if (result.revision_of) {
        try {
          const old = await getArtifactPreview(result.revision_of);
          if (!disposed) setPrevious(old);
        } catch { if (!disposed) setComparisonFailed(true); }
      }
    }).catch(() => { if (!disposed) setError(true); });
    return () => { disposed = true; };
  }, [open, artifactId, reload]);

  const act = async (action: 'download' | 'revise') => {
    if (!data || busy) return;
    setBusy(true);
    try {
      if (action === 'download') {
        const title = data.quality.ready && data.approval_status === 'approved' ? data.title : `审核草稿-${data.title}`;
        await downloadArtifact(data.id, format, title);
      } else {
        const text = instructions.trim();
        if (text.length < 2) return;
        if (request.current.text !== text) request.current = { text, key: crypto.randomUUID() };
        await reviseArtifact(data.id, text, request.current.key);
        if (alive.current) { toast.success('修订任务已提交，原稿已保留'); onQueued?.(); setOpen(false); }
      }
    } catch { if (alive.current) toast.error('操作未完成，请检查资料权限或稍后重试'); }
    finally { if (alive.current) setBusy(false); }
  };

  const renderDocument = (content: string) => <div className="prose prose-sm max-w-none break-words text-foreground dark:prose-invert [&_table]:block [&_table]:max-w-full [&_table]:overflow-x-auto [&_pre]:overflow-x-auto">
    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]} components={{ img: () => null, a: ({ children }) => <span>{children}</span> }}>{content}</ReactMarkdown>
  </div>;

  return <Dialog open={open} onOpenChange={(next) => { if (!busy) setOpen(next); }}>
    <DialogTrigger asChild><Button variant="ghost" size="icon" title="预览与修订" aria-label="预览与修订"><Eye className="h-4 w-4" /></Button></DialogTrigger>
    <DialogContent className="flex max-h-[90dvh] w-[calc(100%-2rem)] max-w-4xl flex-col overflow-hidden">
      <DialogHeader className="shrink-0 pr-6"><DialogTitle className="break-words">{data?.title || '成果预览'}</DialogTitle><DialogDescription>{data ? (data.quality.ready && data.approval_status === 'approved' ? '已审核' : '审核草稿') : '正在读取成果'}</DialogDescription></DialogHeader>
      {error ? <div role="alert" className="flex items-center justify-between gap-3 py-6 text-sm">暂时无法读取成果，或引用资料已变更。<Button variant="outline" size="icon" aria-label="重新加载预览" onClick={() => setReload((value) => value + 1)}><RotateCcw className="h-4 w-4" /></Button></div> : !data ? <Loader2 aria-label="加载预览" className="m-6 h-5 w-5 animate-spin motion-reduce:animate-none" /> : <>
        <Tabs defaultValue="document" className="flex min-h-0 flex-1 flex-col">
          <TabsList className="shrink-0 justify-start"><TabsTrigger value="document">正文</TabsTrigger><TabsTrigger value="checks">交付检查</TabsTrigger>{data.revision_of && <TabsTrigger value="compare">修订对照</TabsTrigger>}</TabsList>
          <div className="min-h-0 flex-1 overflow-y-auto py-4">
            <TabsContent value="document" className="mt-0">{renderDocument(data.content_markdown)}</TabsContent>
            <TabsContent value="checks" className="mt-0 space-y-4 text-sm">
              <p>正文 {data.quality.metrics?.character_count ?? '未统计'} 字 · 要求 {data.requirements.minimum_character_count ?? '未指定'} 字</p>
              <ul className="space-y-2">{data.quality.findings.map((finding, index) => <li key={`${finding.code}-${index}`} className="border-l-2 border-border pl-3">{finding.message}</li>)}</ul>
              <h3 className="font-medium">引用资料</h3><ul className="divide-y">{Array.from(new Map(data.sources.map((source) => [source.document_id, source])).values()).map((source) => <li key={source.document_id} className="break-words py-2">{source.title}<span className="ml-2 text-xs text-muted-foreground">{source.source_version || '版本未标注'}</span></li>)}</ul>
              <p className="text-xs text-muted-foreground">保留步骤用量 {data.usage.total_tokens ?? '未记录'} tokens · 复用 {data.checkpoint_hits} 个步骤</p>
            </TabsContent>
            <TabsContent value="compare" className="mt-0">{previous ? <div className="grid gap-6 md:grid-cols-2"><section className="min-w-0"><h3 className="mb-3 text-sm font-medium">原稿</h3>{renderDocument(previous.content_markdown)}</section><section className="min-w-0"><h3 className="mb-3 text-sm font-medium">修订稿</h3>{renderDocument(data.content_markdown)}</section></div> : <p role="status" className="text-sm">{comparisonFailed ? '原稿不可访问，无法对照' : '正在读取原稿'}</p>}</TabsContent>
          </div>
        </Tabs>
        <div className="shrink-0 space-y-3 border-t pt-3">
          <details><summary className="cursor-pointer text-sm">修改要求</summary><label className="sr-only" htmlFor={`revision-${artifactId}`}>修订要求</label><Textarea id={`revision-${artifactId}`} value={instructions} maxLength={4000} onChange={(event) => setInstructions(event.target.value)} className="my-3 min-h-20" /><Button disabled={busy || instructions.trim().length < 2} onClick={() => void act('revise')}><Send className="mr-2 h-4 w-4" />生成修订稿</Button></details>
          <div className="flex flex-wrap items-center justify-end gap-2"><label className="sr-only" htmlFor={`format-${artifactId}`}>文件格式</label><select id={`format-${artifactId}`} aria-label="文件格式" value={format} onChange={(event) => setFormat(event.target.value as ArtifactOutputFormat)} className="h-9 rounded-md border bg-background px-3 text-sm">{data.requested_formats.map((item) => <option key={item} value={item}>{item.toUpperCase()}</option>)}</select><Button disabled={busy} onClick={() => void act('download')}><Download className="mr-2 h-4 w-4" />{data.quality.ready && data.approval_status === 'approved' ? '下载成果' : '下载审核草稿'}</Button></div>
        </div>
      </>}
    </DialogContent>
  </Dialog>;
}
