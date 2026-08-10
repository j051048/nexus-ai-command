import { useEffect, useMemo, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import {
  Download,
  ExternalLink,
  FileImage,
  FileText,
  Loader2,
  PackageCheck,
  Sheet as SheetIcon,
  ThumbsUp,
  Trash2,
  Trophy,
  XCircle,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { useAuth } from '@/components/auth/AuthContext';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import {
  addDeliverable,
  DELIVERABLE_READY_EVENT,
  type DeliverableEventDetail,
  getRuntimeDownload,
  readDeliverables,
  removeDeliverable,
  writeDeliverables,
} from '@/features/deliverables/deliverableStore';
import { repeatDownload } from '@/features/deliverables/exportContent';
import { listArtifacts, recordArtifactFeedback } from '@/features/deliverables/artifactApi';
import type { DeliverableFormat, DeliverableRecord } from '@/features/deliverables/types';
import { cn } from '@/lib/utils';

const FORMAT_ICON: Record<DeliverableFormat, typeof FileText> = {
  docx: FileText,
  pdf: FileText,
  xlsx: SheetIcon,
  png: FileImage,
  csv: SheetIcon,
  markdown: FileText,
};

function formatSize(size?: number) {
  if (!size) return null;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function DeliverableCenter({ iconOnly = false }: { iconOnly?: boolean }) {
  const { profile, user } = useAuth();
  const navigate = useNavigate();
  const scope = profile?.organization_id || user?.id || 'personal';
  const [records, setRecords] = useState<DeliverableRecord[]>(() => readDeliverables(scope));
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [feedbackId, setFeedbackId] = useState<string | null>(null);
  const [recordedOutcomes, setRecordedOutcomes] = useState<Record<string, string>>({});

  useEffect(() => setRecords(readDeliverables(scope)), [scope]);

  useEffect(() => {
    let cancelled = false;
    void listArtifacts()
      .then((artifacts) => {
        if (cancelled) return;
        const remote: DeliverableRecord[] = artifacts.flatMap((artifact) => (
          artifact.requested_formats.map((format) => ({
            id: `${artifact.id}-${format}`,
            title: artifact.title,
            filename: `${artifact.title}.${format}`,
            format,
            source: 'artifact' as const,
            sourceLabel: '精品成果',
            sourcePath: '/dashboard',
            createdAt: artifact.updated_at || artifact.created_at,
            artifactId: artifact.id,
            versionNumber: artifact.version_number,
            qualityScore: artifact.quality_score,
            approvalStatus: artifact.approval_status,
            downloadAction: {
              type: 'http-blob' as const,
              url: `/api/artifacts/${artifact.id}/download`,
              filename: `${artifact.title}.${format}`,
              params: { format },
            },
          }))
        ));
        const merged = [...remote, ...readDeliverables(scope)]
          .filter((record, index, all) => all.findIndex((item) => item.id === record.id) === index)
          .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())
          .slice(0, 40);
        writeDeliverables(scope, merged);
        setRecords(merged);
      })
      .catch(() => { /* Backend persistence is additive; local results remain available. */ });
    return () => { cancelled = true; };
  }, [scope]);

  useEffect(() => {
    const onReady = (event: Event) => {
      const detail = (event as CustomEvent<DeliverableEventDetail>).detail;
      if (!detail?.record) return;
      setRecords(addDeliverable(scope, detail.record));
    };
    window.addEventListener(DELIVERABLE_READY_EVENT, onReady);
    return () => window.removeEventListener(DELIVERABLE_READY_EVENT, onReady);
  }, [scope]);

  const recentCount = useMemo(() => records.filter((record) => (
    Date.now() - new Date(record.createdAt).getTime() < 24 * 60 * 60 * 1000
  )).length, [records]);

  const openOrDownload = async (record: DeliverableRecord) => {
    const runtimeDownload = getRuntimeDownload(record.id);
    if (!runtimeDownload && !record.downloadAction) {
      navigate(record.sourcePath);
      return;
    }
    setDownloadingId(record.id);
    try {
      if (runtimeDownload) await runtimeDownload();
      else if (record.downloadAction) await repeatDownload(record.downloadAction);
      toast.success(`${record.filename} 已下载`);
    } catch {
      toast.error('成果下载失败，请打开来源后重新生成');
    } finally {
      setDownloadingId(null);
    }
  };

  const submitOutcome = async (
    record: DeliverableRecord,
    outcome: 'used' | 'discarded' | 'won',
  ) => {
    if (!record.artifactId) return;
    setFeedbackId(record.id);
    try {
      await recordArtifactFeedback(
        record.artifactId,
        outcome === 'discarded' ? 2 : 5,
        outcome,
      );
      setRecordedOutcomes((current) => ({ ...current, [record.id]: outcome }));
      toast.success(outcome === 'won' ? '已记录赢单结果' : outcome === 'used' ? '已记录成果被采用' : '已记录未采用');
    } catch {
      toast.error('结果记录失败，请稍后重试');
    } finally {
      setFeedbackId(null);
    }
  };

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          size={iconOnly ? 'icon' : 'sm'}
          className={cn('relative text-muted-foreground hover:text-foreground', iconOnly ? 'h-10 w-10' : 'h-8 gap-1.5 px-2.5')}
          aria-label="打开成果中心"
          data-testid="deliverable-center-trigger"
        >
          <PackageCheck className="h-4 w-4" />
          {!iconOnly && <span>成果</span>}
          {recentCount > 0 && (
            <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground">
              {recentCount > 9 ? '9+' : recentCount}
            </span>
          )}
        </Button>
      </SheetTrigger>
      <SheetContent className="flex w-full flex-col gap-0 p-0 sm:max-w-md">
        <SheetHeader className="border-b px-5 py-5 pr-12">
          <SheetTitle className="flex items-center gap-2 text-base">
            <PackageCheck className="h-4 w-4 text-primary" />成果中心
          </SheetTitle>
          <SheetDescription>方案、报告、表格与图片统一从这里交付。</SheetDescription>
        </SheetHeader>

        <div className="flex items-center justify-between border-b px-5 py-3 text-xs text-muted-foreground">
          <span>最近成果 {records.length} 项</span>
          {records.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => {
                writeDeliverables(scope, []);
                setRecords([]);
              }}
            >
              清空记录
            </Button>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {!records.length ? (
            <div className="flex min-h-80 flex-col items-center justify-center px-8 text-center">
              <PackageCheck className="h-8 w-8 text-muted-foreground/50" />
              <h3 className="mt-4 text-sm font-semibold">成果会自动汇集到这里</h3>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                让 AI 生成方案、报告或表格，完成后即可直接下载。
              </p>
            </div>
          ) : (
            <div className="divide-y">
              {records.map((record) => {
                const Icon = FORMAT_ICON[record.format];
                const canDownload = Boolean(getRuntimeDownload(record.id) || record.downloadAction);
                return (
                  <div key={record.id} className="group flex gap-3 px-5 py-4 hover:bg-muted/30">
                    <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-background text-primary">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{record.title}</div>
                      <div className="mt-1 flex flex-wrap gap-x-2 text-[11px] text-muted-foreground">
                        <span>{record.format.toUpperCase()}</span>
                        <span>{record.sourceLabel}</span>
                        {formatSize(record.sizeBytes) && <span>{formatSize(record.sizeBytes)}</span>}
                        <span>{formatDistanceToNow(new Date(record.createdAt), { addSuffix: true, locale: zhCN })}</span>
                      </div>
                      {(record.qualityScore != null || record.approvalStatus) && (
                        <div className="mt-2 flex items-center gap-1.5">
                          {record.qualityScore != null && (
                            <Badge variant="secondary" className="h-5 px-1.5 text-[10px] font-normal">
                              质量 {Math.round(record.qualityScore)}
                            </Badge>
                          )}
                          {record.approvalStatus && (
                            <Badge variant={record.approvalStatus === 'approved' ? 'default' : 'outline'} className="h-5 px-1.5 text-[10px] font-normal">
                              {record.approvalStatus === 'approved' ? '已审核' : '审核草稿'}
                            </Badge>
                          )}
                        </div>
                      )}
                      {record.artifactId && (
                        <div className="mt-2 flex items-center gap-1 text-[11px]">
                          {recordedOutcomes[record.id] ? (
                            <span className="text-muted-foreground">
                              已回流：{recordedOutcomes[record.id] === 'won' ? '赢单' : recordedOutcomes[record.id] === 'used' ? '采用' : '未采用'}
                            </span>
                          ) : (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 gap-1 px-1.5 text-[11px]"
                                disabled={feedbackId === record.id}
                                onClick={() => void submitOutcome(record, 'used')}
                              >
                                <ThumbsUp className="h-3 w-3" />采用
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 gap-1 px-1.5 text-[11px]"
                                disabled={feedbackId === record.id}
                                onClick={() => void submitOutcome(record, 'won')}
                              >
                                <Trophy className="h-3 w-3" />赢单
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 gap-1 px-1.5 text-[11px] text-muted-foreground"
                                disabled={feedbackId === record.id}
                                onClick={() => void submitOutcome(record, 'discarded')}
                              >
                                <XCircle className="h-3 w-3" />未采用
                              </Button>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => void openOrDownload(record)}
                        aria-label={canDownload ? `下载 ${record.filename}` : `打开 ${record.title}`}
                        title={canDownload ? '再次下载' : '打开来源'}
                      >
                        {downloadingId === record.id
                          ? <Loader2 className="h-4 w-4 animate-spin" />
                          : canDownload ? <Download className="h-4 w-4" /> : <ExternalLink className="h-4 w-4" />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground opacity-0 group-hover:opacity-100"
                        onClick={() => setRecords(removeDeliverable(scope, record.id))}
                        aria-label={`移除 ${record.title}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
