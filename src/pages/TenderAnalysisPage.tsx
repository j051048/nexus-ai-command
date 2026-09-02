import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleDollarSign,
  FileCheck2,
  FileText,
  FolderKanban,
  Loader2,
  Plus,
  Save,
  ShieldCheck,
} from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { AIInsightPanel } from '@/components/ai/AIInsightPanel';
import { ContextAIActionMenu } from '@/components/ai/ContextAIActionMenu';
import { EvidenceDrawer, type EvidenceDrawerItem } from '@/components/ai/EvidenceDrawer';
import { OperationalMetricStrip } from '@/components/common/OperationalMetricStrip';
import { PrecisionPageHeader } from '@/components/common/PrecisionPageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useUser } from '@/contexts/UserContext';
import { TenderProjectDialog } from '@/features/tender/TenderProjectDialog';
import { TenderStageRail } from '@/features/tender/TenderStageRail';
import { TenderWorkspaceContent } from '@/features/tender/TenderWorkspaceContent';
import type { TenderProject, TenderStage, TenderWorkspaceState } from '@/features/tender/types';
import {
  useCreateTenderProject,
  useSaveTenderWorkspace,
  useTenderProjects,
} from '@/features/tender/useTenderWorkspace';
import {
  TENDER_ANALYSIS_STEPS,
  useTenderDocumentAnalysis,
} from '@/features/tender/useTenderDocumentAnalysis';
import {
  createTenderWorkspace,
  mergeReportIntoWorkspace,
  tenderReadiness,
  TENDER_STAGE_DEFINITIONS,
} from '@/features/tender/workspaceModel';

function projectName(project?: TenderProject | null) {
  return project?.title || project?.project_name || '未命名投标项目';
}

function deadlineLabel(project?: TenderProject | null) {
  const raw = project?.deadline || project?.bid_deadline;
  if (!raw) return '截止时间待确认';
  const deadline = new Date(raw);
  const days = Math.ceil((deadline.getTime() - Date.now()) / 86_400_000);
  if (days < 0) return `已截止 ${Math.abs(days)} 天`;
  if (days === 0) return '今天截止';
  return `${days} 天后截止`;
}

function stageNextAction(stage: TenderStage, readiness: ReturnType<typeof tenderReadiness>) {
  if (stage === 'intake') return { title: '上传招标文件并开始风险审阅', summary: '系统先提取否决项、评分项和证据缺口，再进入逐条应答。' };
  if (stage === 'review') return { title: '先复核高风险条款', summary: `已识别 ${readiness.totalRequirements} 条要求，${readiness.gaps} 条需要优先确认。` };
  if (stage === 'matrix') return { title: '补齐响应、证据与责任人', summary: `当前已完成 ${readiness.answered}/${readiness.totalRequirements} 条应答。` };
  if (stage === 'draft') return { title: '按核验结果生成章节草稿', summary: `已有 ${readiness.approvedSections} 个章节通过人工批准。` };
  if (stage === 'quality') return { title: '完成定稿前人工门禁', summary: `已通过 ${readiness.passedGates} 项复核，外发动作不会自动执行。` };
  return { title: readiness.canDeliver ? '整理最终交付物' : '先处理剩余缺口', summary: readiness.canDeliver ? '已具备定稿条件，可生成整本草稿并导出材料。' : '高风险项和必检门禁未清零，暂不建议定稿。' };
}

export function TenderAnalysisPage() {
  const { user } = useUser();
  const [searchParams, setSearchParams] = useSearchParams();
  const [showHistory, setShowHistory] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [workspace, setWorkspace] = useState<TenderWorkspaceState>(() => createTenderWorkspace());
  const mergedReportRef = useRef<string | null>(null);

  const projectsQuery = useTenderProjects();
  const createProject = useCreateTenderProject();
  const selectedProjectId = Number(searchParams.get('project') || 0) || null;
  const selectedProject = useMemo(
    () => projectsQuery.data?.find((project) => project.id === selectedProjectId) || null,
    [projectsQuery.data, selectedProjectId],
  );
  const saveWorkspace = useSaveTenderWorkspace(selectedProjectId);
  const analysis = useTenderDocumentAnalysis(user?.id);

  useEffect(() => {
    if (selectedProject?.workspace) {
      setWorkspace({ ...createTenderWorkspace(), ...selectedProject.workspace });
      mergedReportRef.current = null;
    }
  }, [selectedProject?.id, selectedProject?.workspace]);

  useEffect(() => {
    if (!selectedProjectId && projectsQuery.data?.length) {
      setSearchParams({ project: String(projectsQuery.data[0].id) }, { replace: true });
    }
  }, [projectsQuery.data, selectedProjectId, setSearchParams]);

  useEffect(() => {
    if (!analysis.report || mergedReportRef.current === analysis.report) return;
    mergedReportRef.current = analysis.report;
    setWorkspace((current) => mergeReportIntoWorkspace(
      current,
      analysis.report || '',
      analysis.docId,
      analysis.currentDocumentName,
    ));
  }, [analysis.currentDocumentName, analysis.docId, analysis.report]);

  const readiness = tenderReadiness(workspace);
  const nextAction = stageNextAction(workspace.active_stage, readiness);
  const completedStages = useMemo<TenderStage[]>(() => {
    const completed: TenderStage[] = [];
    if (workspace.source_document_id || analysis.report) completed.push('intake');
    if (analysis.report && workspace.requirements.length) completed.push('review');
    if (readiness.answered > 0 && readiness.gaps === 0) completed.push('matrix');
    if (workspace.draft_sections.some((section) => section.status === 'approved')) completed.push('draft');
    if (workspace.review_gates.filter((gate) => gate.required).every((gate) => gate.status === 'passed')) completed.push('quality');
    if (readiness.canDeliver) completed.push('delivery');
    return completed;
  }, [analysis.report, readiness, workspace]);

  const changeStage = (active_stage: TenderStage) => setWorkspace((current) => ({ ...current, active_stage }));
  const openAssistant = (prompt: string) => {
    window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
  };

  const handleCreate = async (input: Parameters<typeof createProject.mutateAsync>[0]) => {
    const project = await createProject.mutateAsync(input);
    setSearchParams({ project: String(project.id) });
    setWorkspace(project.workspace || createTenderWorkspace());
    setCreateOpen(false);
    toast.success('投标项目已创建');
  };

  const handleSave = async () => {
    await saveWorkspace.mutateAsync(workspace);
    toast.success('投标工作区已保存');
  };

  const activeDefinition = TENDER_STAGE_DEFINITIONS.find((stage) => stage.id === workspace.active_stage);
  const selectedName = projectName(selectedProject);
  const evidenceItems = useMemo<EvidenceDrawerItem[]>(() => {
    const matrixItems = workspace.response_matrix.map((requirement) => ({
      id: requirement.id,
      title: requirement.requirement,
      description: requirement.source_excerpt,
      status: requirement.status === 'ready' && requirement.evidence_ref ? 'verified' as const : requirement.evidence_ref ? 'pending' as const : 'gap' as const,
      source: requirement.evidence_ref || workspace.source_document_name || undefined,
    }));
    if (workspace.source_document_name) {
      matrixItems.unshift({
        id: `source-${workspace.source_document_id || workspace.source_document_name}`,
        title: workspace.source_document_name,
        description: '招标原文',
        status: 'verified' as const,
        source: '项目源文件',
      });
    }
    return matrixItems.slice(0, 40);
  }, [workspace.response_matrix, workspace.source_document_id, workspace.source_document_name]);

  return (
    <div className="mx-auto max-w-[1320px] space-y-5 pb-20" data-testid="tender-workspace">
      <PrecisionPageHeader
        eyebrow="科学仪器投标作战"
        title="投标作战台"
        description="从招标审阅、应答矩阵到标书草拟和定稿交付，全程保留原文证据与人工确认。"
        icon={ShieldCheck}
        status={selectedProjectId ? {
          label: readiness.canDeliver ? '可定稿' : '准备中',
          detail: `${readiness.gaps} 项缺口`,
          tone: readiness.canDeliver ? 'success' : readiness.gaps > 0 ? 'warning' : 'info',
        } : { label: '待建项目', tone: 'neutral' }}
        actions={<>
          <select
            aria-label="选择投标项目"
            value={selectedProjectId || ''}
            onChange={(event) => setSearchParams(event.target.value ? { project: event.target.value } : {})}
            className="h-9 min-w-56 rounded-md border bg-background px-3 text-sm"
          >
            {!projectsQuery.data?.length && <option value="">暂无投标项目</option>}
            {projectsQuery.data?.map((project) => <option key={project.id} value={project.id}>{projectName(project)}</option>)}
          </select>
          <Button variant="outline" onClick={() => setCreateOpen(true)}><Plus className="mr-2 h-4 w-4" />新建项目</Button>
          <Button onClick={handleSave} disabled={!selectedProjectId || saveWorkspace.isPending}>
            {saveWorkspace.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            保存进度
          </Button>
        </>}
      />

      {projectsQuery.isError && (
        <div className="border-l-2 border-amber-500 bg-amber-50/60 px-4 py-3 text-sm text-amber-900">
          投标项目服务暂不可用，标书审阅仍可继续；项目进度将在服务恢复后保存。
        </div>
      )}

      <OperationalMetricStrip
        ariaLabel="投标项目状态"
        metrics={[
          { label: '当前项目', value: selectedProject ? selectedName : '待创建', detail: workspace.source_document_name || '尚未绑定招标文件', icon: <FolderKanban /> },
          { label: '截止节点', value: deadlineLabel(selectedProject), detail: '以招标文件为准', tone: deadlineLabel(selectedProject).includes('截止') && !deadlineLabel(selectedProject).includes('待确认') ? 'warning' : 'default', icon: <CalendarClock /> },
          { label: '预计金额', value: selectedProject?.estimated_value ? `¥${Number(selectedProject.estimated_value).toLocaleString('zh-CN')}` : '待确认', detail: '商务口径需人工核对', icon: <CircleDollarSign /> },
          { label: '投标准备度', value: `${readiness.score}%`, detail: readiness.canDeliver ? '门禁已通过' : `${readiness.answered}/${readiness.totalRequirements} 条已应答`, tone: readiness.canDeliver ? 'success' : 'warning', icon: <CheckCircle2 /> },
        ]}
      />

      <AIInsightPanel
        surfaceId="tender-next-action"
        variant="compact"
        icon={FileCheck2}
        title={nextAction.title}
        summary={nextAction.summary}
        trustLevel={analysis.report ? 'high' : analysis.file ? 'medium' : 'low'}
        score={analysis.report ? 88 : analysis.file ? 72 : 50}
        stats={[
          { label: '当前阶段', value: activeDefinition?.shortLabel || '立项' },
          { label: '风险缺口', value: `${readiness.gaps} 项` },
        ]}
        actions={[
          {
            label: workspace.active_stage === 'delivery' ? '生成整本草稿' : '让 AI 辅助当前步骤',
            variant: 'default',
            onClick: () => openAssistant(`请协助推进投标项目“${selectedName}”的“${activeDefinition?.label || '当前'}”步骤。先读取已有项目、招标文件与应答矩阵上下文，列出证据缺口；任何参数、资质、报价和外发动作都必须人工确认。`),
          },
        ]}
      />

      <section className="flex flex-wrap justify-end gap-2" aria-label="投标快捷操作">
        <EvidenceDrawer items={evidenceItems} title="投标原文与应答依据" />
        <ContextAIActionMenu label="AI 辅助" actions={[
          { label: '检查废标风险', prompt: `请检查投标项目“${selectedName}”的否决项、资格条件、签章、有效期和强制参数。按风险高低列出，并引用招标原文。` },
          { label: '补齐应答证据', prompt: `请检查投标项目“${selectedName}”的应答矩阵，只列出缺少企业资料证据或责任人的条目，不得编造参数与资质。` },
          { label: '审校商务口径', prompt: `请复核投标项目“${selectedName}”的报价、交期、付款、质保和售后口径是否一致，只输出冲突和待确认项。` },
        ]} />
      </section>

      <TenderStageRail activeStage={workspace.active_stage} onStageChange={changeStage} completedStages={completedStages} />

      <main className="min-h-[430px] border bg-background p-5 md:p-7">
        {!selectedProjectId && !projectsQuery.isLoading ? (
          <div className="flex min-h-[360px] flex-col items-center justify-center text-center">
            <FolderKanban className="h-8 w-8 text-muted-foreground" />
            <h2 className="mt-4 text-base font-semibold">先建立投标项目</h2>
            <p className="mt-1 max-w-md text-sm text-muted-foreground">项目用于集中管理招标文件、应答矩阵、章节草稿、复核门禁和最终交付物。</p>
            <Button className="mt-5" onClick={() => setCreateOpen(true)}><Plus className="mr-2 h-4 w-4" />新建投标项目</Button>
          </div>
        ) : (
          <TenderWorkspaceContent
            stage={workspace.active_stage}
            workspace={workspace}
            report={analysis.report}
            file={analysis.file}
            analyzing={analysis.analyzing}
            progress={analysis.progress}
            currentStep={analysis.currentStep}
            steps={TENDER_ANALYSIS_STEPS}
            projectName={selectedName}
            onFileChange={analysis.onFileChange}
            onStartAnalysis={() => {
              changeStage('review');
              void analysis.startAnalysis();
            }}
            onExportPDF={analysis.exportPDF}
            onWorkspaceChange={setWorkspace}
            onAIAction={openAssistant}
          />
        )}
      </main>

      <section className="border bg-background">
        <button type="button" onClick={() => setShowHistory((current) => !current)} className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-medium hover:bg-muted/40">
          <FileText className="h-4 w-4 text-muted-foreground" />历史分析记录
          <Badge variant="secondary">{analysis.historyDocs.length}</Badge>
          {showHistory ? <ChevronUp className="ml-auto h-4 w-4" /> : <ChevronDown className="ml-auto h-4 w-4" />}
        </button>
        {showHistory && (
          <div className="divide-y border-t">
            {analysis.historyLoading && <div className="flex items-center justify-center p-6 text-sm text-muted-foreground"><Loader2 className="mr-2 h-4 w-4 animate-spin" />加载记录</div>}
            {!analysis.historyLoading && !analysis.historyDocs.length && <div className="p-6 text-center text-sm text-muted-foreground">暂无历史分析</div>}
            {analysis.historyDocs.map((document) => (
              <button key={document.id} type="button" onClick={() => { analysis.loadHistoryDocument(document); changeStage('review'); }} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/40">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate text-sm font-medium">{document.name}</span>
                <span className="text-xs text-muted-foreground">{new Date(document.created_at).toLocaleDateString('zh-CN')}</span>
                <Badge variant={document.status === 'ready' || document.status === 'success' ? 'default' : 'secondary'}>{document.status === 'ready' || document.status === 'success' ? '已完成' : '处理中'}</Badge>
              </button>
            ))}
          </div>
        )}
      </section>

      <TenderProjectDialog open={createOpen} onOpenChange={setCreateOpen} onSubmit={handleCreate} pending={createProject.isPending} />
    </div>
  );
}
