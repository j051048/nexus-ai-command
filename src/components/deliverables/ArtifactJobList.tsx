import { useEffect, useState } from 'react';
import { Download, Loader2, RotateCcw, X } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { cancelArtifactJob, downloadArtifact, listArtifactJobs, retryArtifactJob, type ArtifactGenerationJob } from '@/features/deliverables/artifactApi';

const STATUS_LABEL: Record<ArtifactGenerationJob['status'], string> = {
  queued: '排队中', running: '制作中', cancelling: '正在取消',
  cancelled: '已取消', completed: '可下载', failed: '未完成',
};

export function ArtifactJobList({ scope }: { scope: string }) {
  const [jobs, setJobs] = useState<ArtifactGenerationJob[]>([]);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    setJobs([]);
    const refresh = async () => {
      try {
        const rows = await listArtifactJobs();
        if (!disposed) { setJobs(rows); setError(false); }
      } catch {
        if (!disposed) setError(true);
      } finally {
        if (!disposed) timer = setTimeout(() => void refresh(), 10000);
      }
    };
    void refresh();
    return () => { disposed = true; clearTimeout(timer); };
  }, [scope, revision]);

  const act = async (job: ArtifactGenerationJob, action: 'cancel' | 'retry' | 'download') => {
    setBusy(job.id);
    try {
      if (action === 'cancel') await cancelArtifactJob(job.id);
      else if (action === 'retry') await retryArtifactJob(job.id);
      else if (job.result?.id) {
        await downloadArtifact(job.result.id, job.result.requested_formats[0] || 'docx', job.result.title);
      }
      setRevision((value) => value + 1);
    } catch {
      toast.error('操作未完成，请稍后重试');
    } finally { setBusy(null); }
  };

  if (!jobs.length && !error) return null;
  return <section className="border-b px-5 py-3" aria-label="最近制作任务">
    <h3 className="mb-2 text-xs font-medium text-muted-foreground">最近制作</h3>
    {error && <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground" role="status">
      暂时无法更新任务
      <Button variant="ghost" size="icon" title="重新连接" aria-label="重新连接" onClick={() => setRevision((value) => value + 1)}><RotateCcw className="h-4 w-4" /></Button>
    </div>}
    <ul className="divide-y">
      {jobs.map((job) => {
        const active = ['queued', 'running', 'cancelling'].includes(job.status);
        const label = job.status === 'completed' && job.result?.quality?.ready === false ? '待修订' : STATUS_LABEL[job.status];
        return <li key={job.id} className="flex items-center gap-3 py-2">
          {active ? <Loader2 className="h-4 w-4 shrink-0 animate-spin motion-reduce:animate-none text-muted-foreground" /> : <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground" />}
          <div className="min-w-0 flex-1">
            <p className="break-words text-sm">{job.result?.title || `成果任务 ${job.id.slice(0, 8)}`}</p>
            <p className="text-xs text-muted-foreground" role="status">{label}{active ? ` · ${job.progress}%` : ''}</p>
          </div>
          {['queued', 'running'].includes(job.status) && <Button variant="ghost" size="icon" disabled={busy === job.id} title="取消制作" aria-label="取消制作" onClick={() => void act(job, 'cancel')}><X className="h-4 w-4" /></Button>}
          {job.status === 'failed' && job.attempt < job.max_attempts && <Button variant="ghost" size="icon" disabled={busy === job.id} title="重试任务" aria-label="重试任务" onClick={() => void act(job, 'retry')}><RotateCcw className="h-4 w-4" /></Button>}
          {job.status === 'completed' && job.result?.id && <Button variant="ghost" size="icon" disabled={busy === job.id} title={label === '待修订' ? '下载审核草稿' : '下载成果'} aria-label="下载任务成果" onClick={() => void act(job, 'download')}><Download className="h-4 w-4" /></Button>}
        </li>;
      })}
    </ul>
  </section>;
}
