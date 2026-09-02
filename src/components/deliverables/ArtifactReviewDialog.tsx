import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  Check,
  Download,
  FileCheck2,
  FileText,
  Loader2,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { ArtifactSourcePicker } from '@/components/deliverables/ArtifactSourcePicker';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import {
  downloadArtifact,
  cancelArtifactJob,
  generateArtifact,
  recordArtifactFeedback,
  type ArtifactOutputFormat,
  type ArtifactResult,
  type ArtifactType,
} from '@/features/deliverables/artifactApi';
import { announceDeliverable } from '@/features/deliverables/deliverableStore';
import { inferTargetCharacterCount } from '@/features/deliverables/deliverableEligibility';
import { titleFromContent } from '@/features/deliverables/exportContent';


const ARTIFACT_TYPES: Array<{ value: ArtifactType; label: string }> = [
  { value: 'customer_solution', label: '客户解决方案' },
  { value: 'tender', label: '投标文件 / 标书' },
  { value: 'technical_report', label: '技术 / 分析报告' },
  { value: 'competitor_analysis', label: '竞品对比分析' },
  { value: 'service_proposal', label: '售后 / 维保方案' },
  { value: 'policy_brief', label: '政策与合规简报' },
];

const PHASES = [
  { label: '盘点企业资料', icon: Search },
  { label: '制定客户策略', icon: Sparkles },
  { label: '协同分章撰写', icon: FileText },
  { label: '总编统一成稿', icon: FileCheck2 },
  { label: '独立质量评审', icon: ShieldCheck },
  { label: '专业排版交付', icon: Download },
];

const CONTENT_DEPTHS = [
  { value: 1500, label: '精简 · 约 1500 字' },
  { value: 2200, label: '标准 · 约 2200 字' },
  { value: 3000, label: '完整 · 不少于 3000 字' },
  { value: 5000, label: '深度 · 不少于 5000 字' },
];

function phaseForStage(stage: string) {
  if (['queued', 'starting', 'template_selection', 'evidence_compilation'].includes(stage)) return 0;
  if (stage === 'delivery_strategy') return 1;
  if (stage === 'deep_writing') return 2;
  if (stage === 'editorial_synthesis') return 3;
  if (['quality_review', 'quality_repair'].includes(stage)) return 4;
  if (['persistence', 'completed'].includes(stage)) return 5;
  return 0;
}

interface ArtifactReviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  content: string;
  originalRequest: string;
  defaultType: ArtifactType;
  sessionId?: string;
}

export function ArtifactReviewDialog({
  open,
  onOpenChange,
  content,
  originalRequest,
  defaultType,
  sessionId,
}: ArtifactReviewDialogProps) {
  const [title, setTitle] = useState(() => {
    const candidate = titleFromContent(content);
    return candidate === 'AI生成成果' ? '' : candidate;
  });
  const [artifactType, setArtifactType] = useState<ArtifactType>(defaultType);
  const [targetCharacters, setTargetCharacters] = useState(() => inferTargetCharacterCount(originalRequest, defaultType));
  const [audience, setAudience] = useState<'internal' | 'customer'>('customer');
  const [formats, setFormats] = useState<ArtifactOutputFormat[]>(['docx', 'pdf']);
  const [customer, setCustomer] = useState('');
  const [industry, setIndustry] = useState('');
  const [scenario, setScenario] = useState('');
  const [factsConfirmed, setFactsConfirmed] = useState(false);
  const [promisesConfirmed, setPromisesConfirmed] = useState(false);
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>([]);
  const [generating, setGenerating] = useState(false);
  const [phase, setPhase] = useState(0);
  const [jobProgress, setJobProgress] = useState(0);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [result, setResult] = useState<ArtifactResult | null>(null);
  const [downloading, setDownloading] = useState<ArtifactOutputFormat | null>(null);
  const [feedback, setFeedback] = useState<'used' | 'edited' | null>(null);

  const canSubmit = useMemo(
    () => formats.length > 0 && (audience === 'internal' || (factsConfirmed && promisesConfirmed)),
    [audience, factsConfirmed, formats.length, promisesConfirmed],
  );

  const toggleFormat = (format: ArtifactOutputFormat) => {
    setFormats((current) => current.includes(format)
      ? current.filter((item) => item !== format)
      : [...current, format]);
  };

  const addToDeliverableCenter = (artifact: ArtifactResult) => {
    artifact.requested_formats.forEach((format) => {
      announceDeliverable({
        id: `${artifact.id}-${format}`,
        title: artifact.title,
        filename: `${artifact.title}.${format}`,
        format,
        source: 'artifact',
        sourceLabel: '精品成果',
        sourcePath: `${window.location.pathname}${window.location.search}`,
        qualityScore: artifact.quality.score,
        approvalStatus: artifact.approval_status,
        artifactId: artifact.id,
        versionNumber: artifact.version_number,
        evidenceCount: artifact.evidence.count,
        evidenceCoverage: artifact.evidence.coverage,
        characterCount: artifact.quality.metrics?.character_count,
        downloadAction: {
          type: 'http-blob',
          url: `/api/artifacts/${artifact.id}/download`,
          filename: `${artifact.title}.${format}`,
          params: { format },
        },
      });
    });
  };

  const handleGenerate = async () => {
    if (!canSubmit) {
      toast.error('对外成果需先确认事实与承诺边界');
      return;
    }
    setGenerating(true);
    setResult(null);
    setPhase(0);
    setJobProgress(0);
    setActiveJobId(null);
    try {
      const artifact = await generateArtifact({
        original_request: originalRequest || `将当前内容整理为${ARTIFACT_TYPES.find((item) => item.value === artifactType)?.label}`,
        source_content: content,
        title: title.trim() || undefined,
        artifact_type: artifactType,
        audience,
        requested_formats: formats,
        customer_context: {
          customer_name: customer,
          industry,
          application_scenario: scenario,
        },
        selected_document_ids: selectedDocuments,
        target_character_count: targetCharacters,
        generation_mode: 'deep',
        session_id: sessionId,
        review_confirmed: audience === 'internal' || (factsConfirmed && promisesConfirmed),
      }, (job) => {
        setActiveJobId(job.id);
        setJobProgress(job.progress);
        setPhase(phaseForStage(job.stage));
      });
      setPhase(PHASES.length - 1);
      setJobProgress(100);
      setResult(artifact);
      addToDeliverableCenter(artifact);
      if (artifact.quality.ready) {
        const primaryFormat = formats[0];
        await downloadArtifact(artifact.id, primaryFormat, artifact.title);
        toast.success('精品成果已生成并下载，其他格式已保存到成果中心');
      } else {
        toast.warning('已生成审核草稿，但仍有待核验项，请查看质量说明');
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '精品成果生成失败';
      toast.error(message);
    } finally {
      setGenerating(false);
      setActiveJobId(null);
    }
  };

  const handleCancel = async () => {
    if (!activeJobId || cancelling) return;
    setCancelling(true);
    try {
      await cancelArtifactJob(activeJobId);
      toast.info('已请求停止制作，当前步骤结束后任务会安全退出');
    } catch {
      toast.error('暂时无法取消任务，请稍后重试');
    } finally {
      setCancelling(false);
    }
  };

  const handleFeedback = async (outcome: 'used' | 'edited') => {
    if (!result || feedback) return;
    try {
      await recordArtifactFeedback(result.id, outcome === 'used' ? 5 : 3, outcome);
      setFeedback(outcome);
      toast.success('反馈已记录，将用于改进后续成果');
    } catch {
      toast.error('反馈记录失败，请稍后重试');
    }
  };

  const handleDownload = async (format: ArtifactOutputFormat) => {
    if (!result) return;
    setDownloading(format);
    try {
      await downloadArtifact(result.id, format, result.title);
      toast.success(`${format.toUpperCase()} 已下载`);
    } catch {
      toast.error('下载失败，请稍后重试');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] overflow-y-auto p-0 sm:max-w-2xl">
        <DialogHeader className="border-b px-6 py-5 pr-12 text-left">
          <DialogTitle className="flex items-center gap-2 text-base">
            <FileCheck2 className="h-4 w-4 text-primary" />
            制作精品成果
          </DialogTitle>
          <DialogDescription>
            重新编排资料分析、客户策略、分章写作、总编与独立质检，不会直接复制当前回答。
          </DialogDescription>
        </DialogHeader>

        {generating ? (
          <div className="px-6 py-10">
            <div className="mx-auto max-w-md">
              <div className="mb-5 flex items-center justify-between text-sm">
                <span className="font-medium">{PHASES[phase].label}</span>
                <span className="text-xs text-muted-foreground">{phase + 1} / {PHASES.length}</span>
              </div>
              <Progress value={jobProgress} className="h-1.5" />
              <div className="mt-8 grid grid-cols-3 gap-4 sm:grid-cols-6">
                {PHASES.map((item, index) => {
                  const Icon = item.icon;
                  const active = index <= phase;
                  return (
                    <div key={item.label} className="text-center">
                      <div className={`mx-auto flex h-9 w-9 items-center justify-center rounded-full border ${active ? 'border-primary bg-primary/8 text-primary' : 'text-muted-foreground/40'}`}>
                        {index < phase ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                      </div>
                      <div className="mt-2 text-[11px] leading-4 text-muted-foreground">{item.label}</div>
                    </div>
                  );
                })}
              </div>
              <p className="mt-8 text-center text-xs text-muted-foreground">
                深度成果通常需要 1-3 分钟，只有通过结构与语义双重质检后才会标记为精品成果。
              </p>
              <div className="mt-4 flex justify-center">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={!activeJobId || cancelling}
                  onClick={() => void handleCancel()}
                >
                  {cancelling ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : null}
                  停止制作
                </Button>
              </div>
            </div>
          </div>
        ) : result ? (
          <div className="space-y-0">
            <div className="flex items-start justify-between gap-4 border-b px-6 py-5">
              <div>
                <div className="text-sm font-semibold">{result.title}</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {result.artifact_code} · v{result.version_number} · {result.evidence.count} 条证据
                </div>
                {result.quality.metrics && (
                  <div className="mt-1 text-xs text-muted-foreground">
                    正文 {result.quality.metrics.character_count ?? 0} / {result.quality.metrics.target_character_count ?? targetCharacters} 字
                    {' · '}表格 {result.quality.metrics.table_count ?? 0} / {result.quality.metrics.minimum_table_count ?? 0}
                  </div>
                )}
                {result.orchestration && (
                  <div className="mt-1 text-xs text-muted-foreground">
                    深度编排 {result.orchestration.stage_count} 步
                    {' · '}语义质检 {Math.round(result.orchestration.semantic_score)}
                    {result.orchestration.repair_count > 0
                      ? ` · 自动返工 ${result.orchestration.repair_count} 次`
                      : ''}
                  </div>
                )}
              </div>
              <Badge variant={result.quality.ready ? 'default' : 'secondary'}>
                质量 {Math.round(result.quality.score)}
              </Badge>
            </div>
            <div className="grid gap-0 md:grid-cols-[1fr_220px]">
              <div className="border-b px-6 py-5 md:border-b-0 md:border-r">
                <h3 className="text-sm font-semibold">交付状态</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {result.quality.ready
                    ? '结构、证据与引用已通过质量门，可以下载并进入最终人工审阅。'
                    : '已完成内容整理，但证据或事实仍不足，下载版本会标记为审核草稿。'}
                </p>
                {result.verification_items.length > 0 && (
                  <div className="mt-4">
                    <div className="text-xs font-medium">待核验</div>
                    <ul className="mt-2 space-y-1 text-xs leading-5 text-muted-foreground">
                      {result.verification_items.slice(0, 5).map((item) => <li key={item}>· {item}</li>)}
                    </ul>
                  </div>
                )}
                {!result.quality.ready && result.quality.findings.length > 0 && (
                  <div className="mt-4 flex gap-2 border-l-2 border-amber-500 pl-3 text-xs leading-5 text-muted-foreground">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
                    <span>{result.quality.findings.slice(0, 3).map((item) => item.message).join('；')}</span>
                  </div>
                )}
                <div className="mt-5 flex items-center gap-2 border-t pt-4">
                  <span className="mr-auto text-xs text-muted-foreground">这份成果是否可用？</span>
                  <Button size="sm" variant={feedback === 'used' ? 'default' : 'outline'} onClick={() => void handleFeedback('used')} disabled={Boolean(feedback)}>
                    可直接使用
                  </Button>
                  <Button size="sm" variant={feedback === 'edited' ? 'default' : 'ghost'} onClick={() => void handleFeedback('edited')} disabled={Boolean(feedback)}>
                    需要修改
                  </Button>
                </div>
              </div>
              <div className="px-6 py-5">
                <div className="text-xs font-medium">下载格式</div>
                <div className="mt-3 space-y-2">
                  {result.requested_formats.map((format) => (
                    <Button
                      key={format}
                      variant="outline"
                      className="w-full justify-between"
                      onClick={() => void handleDownload(format)}
                      disabled={downloading === format}
                    >
                      <span>{format.toUpperCase()}</span>
                      {downloading === format
                        ? <Loader2 className="h-4 w-4 animate-spin" />
                        : <Download className="h-4 w-4" />}
                    </Button>
                  ))}
                </div>
                <p className="mt-3 text-[11px] leading-4 text-muted-foreground">此后可在顶部“成果”中反复下载。</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-0">
            <div className="grid gap-4 border-b px-6 py-5 md:grid-cols-2">
              <label className="space-y-2 text-xs font-medium">
                成果类型
                <Select value={artifactType} onValueChange={(value) => {
                  const nextType = value as ArtifactType;
                  setArtifactType(nextType);
                  setTargetCharacters(inferTargetCharacterCount(originalRequest, nextType));
                }}>
                  <SelectTrigger className="mt-2"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ARTIFACT_TYPES.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </label>
              <label className="space-y-2 text-xs font-medium">
                使用场景
                <Select value={audience} onValueChange={(value) => setAudience(value as 'internal' | 'customer')}>
                  <SelectTrigger className="mt-2"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="customer">发给客户 / 对外</SelectItem>
                    <SelectItem value="internal">内部分析与协作</SelectItem>
                  </SelectContent>
                </Select>
              </label>
              <label className="space-y-2 text-xs font-medium md:col-span-2">
                内容深度
                <Select value={String(targetCharacters)} onValueChange={(value) => setTargetCharacters(Number(value))}>
                  <SelectTrigger className="mt-2"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CONTENT_DEPTHS.map((item) => <SelectItem key={item.value} value={String(item.value)}>{item.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </label>
              <label className="space-y-2 text-xs font-medium md:col-span-2">
                成果名称
                <Input className="mt-2" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="留空则由 AI 根据客户与任务生成正式标题" />
              </label>
            </div>

            <div className="grid gap-4 border-b px-6 py-5 md:grid-cols-2">
              <label className="space-y-2 text-xs font-medium">
                客户名称 <span className="font-normal text-muted-foreground">可选</span>
                <Input className="mt-2" value={customer} onChange={(event) => setCustomer(event.target.value)} placeholder="例如：某市市场监督管理局" />
              </label>
              <label className="space-y-2 text-xs font-medium">
                行业 / 地区 <span className="font-normal text-muted-foreground">可选</span>
                <Input className="mt-2" value={industry} onChange={(event) => setIndustry(event.target.value)} placeholder="例如：食品安全 · 泸州市" />
              </label>
              <label className="space-y-2 text-xs font-medium md:col-span-2">
                本次重点 <span className="font-normal text-muted-foreground">可选</span>
                <Textarea className="mt-2 min-h-20" value={scenario} onChange={(event) => setScenario(event.target.value)} placeholder="预算、应用场景、交付期限或必须强调的价值" />
              </label>
            </div>

            <ArtifactSourcePicker selected={selectedDocuments} onChange={setSelectedDocuments} />

            <div className="border-b px-6 py-5">
              <div className="text-xs font-medium">需要的格式</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(['docx', 'pdf', 'xlsx'] as ArtifactOutputFormat[]).map((format) => (
                  <Button key={format} type="button" variant={formats.includes(format) ? 'default' : 'outline'} size="sm" onClick={() => toggleFormat(format)}>
                    <FileText className="mr-1.5 h-3.5 w-3.5" />{format.toUpperCase()}
                  </Button>
                ))}
              </div>
            </div>

            {audience === 'customer' && (
              <div className="space-y-3 px-6 py-5">
                <label className="flex cursor-pointer items-start gap-3 text-xs leading-5">
                  <Checkbox checked={factsConfirmed} onCheckedChange={(value) => setFactsConfirmed(value === true)} />
                  <span>我理解 AI 只会引用企业资料；缺少证据的型号、参数、案例会标记为“待核验”。</span>
                </label>
                <label className="flex cursor-pointer items-start gap-3 text-xs leading-5">
                  <Checkbox checked={promisesConfirmed} onCheckedChange={(value) => setPromisesConfirmed(value === true)} />
                  <span>价格、交期、性能保证与售后承诺仍需负责人最终确认。</span>
                </label>
              </div>
            )}
          </div>
        )}

        <DialogFooter className="border-t px-6 py-4">
          {result ? (
            <Button onClick={() => onOpenChange(false)}>完成</Button>
          ) : !generating ? (
            <>
              <Button variant="ghost" onClick={() => onOpenChange(false)}>取消</Button>
              <Button onClick={() => void handleGenerate()} disabled={!canSubmit}>
                <Sparkles className="mr-2 h-4 w-4" />开始制作
              </Button>
            </>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
