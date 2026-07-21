import { useEffect, useMemo, useRef, useState } from 'react';
import { BookOpenCheck, CheckCircle2, FileStack, FolderKanban, Gauge, Loader2, Plus, Save, Sparkles } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { ContextAIActionMenu } from '@/components/ai/ContextAIActionMenu';
import { EvidenceDrawer, type EvidenceDrawerItem } from '@/components/ai/EvidenceDrawer';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { SolutionProjectDialog } from '@/features/solution/SolutionProjectDialog';
import { SolutionStageRail } from '@/features/solution/SolutionStageRail';
import { SolutionWorkspaceContent } from '@/features/solution/SolutionWorkspaceContent';
import type { SolutionStage, SolutionWorkspaceState } from '@/features/solution/types';
import {
  downloadSolution,
  useCreateTenderFromSolution,
  useCreateSolutionProject,
  useExtractSolutionRequirements,
  useGenerateSolution,
  usePromoteSolutionTemplate,
  useSaveSolutionWorkspace,
  useSolutionAnalytics,
  useSolutionContextOptions,
  useSolutionOutcome,
  useSolutionFeedback,
  useSolutionProjects,
  useSolutionVersions,
} from '@/features/solution/useSolutionWorkspace';
import {
  completedSolutionStages,
  createSolutionWorkspace,
  solutionReadiness,
  SOLUTION_STAGE_DEFINITIONS,
} from '@/features/solution/workspaceModel';

function nextAction(stage: SolutionStage, readiness: ReturnType<typeof solutionReadiness>) {
  if (stage === 'brief') return ['先补齐客户事实', '明确应用场景、预算和仪器谱系，再让 AI 检索企业资料。'];
  if (stage === 'requirements') return ['核验必选需求', `仍有 ${readiness.mustOpen} 项必选需求需要证据。`];
  if (stage === 'configuration') return ['比较三档配置', '选择推荐方案，并核对型号、关键参数与服务范围。'];
  if (stage === 'draft') return ['审阅方案章节', `当前 ${readiness.approvedSections} 个章节已批准，引用了 ${readiness.evidenceCount} 条证据。`];
  if (stage === 'review') return ['完成外发门禁', `已通过 ${readiness.passedGates}/3 项人工确认。`];
  return [readiness.canExport ? '导出并记录结果' : '先补齐未完成项', readiness.canExport ? '方案已具备外发条件，导出不会再次消耗模型费用。' : '系统会继续阻止未经核验的方案外发。'];
}

export default function SolutionWorkspacePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const openedCustomerRef = useRef<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [workspace, setWorkspace] = useState<SolutionWorkspaceState>(() => createSolutionWorkspace());
  const projectsQuery = useSolutionProjects();
  const contextQuery = useSolutionContextOptions();
  const analyticsQuery = useSolutionAnalytics();
  const createProject = useCreateSolutionProject();
  const selectedProjectId = searchParams.get('project');
  const initialCustomerId = searchParams.get('customer');
  const selectedProject = useMemo(
    () => projectsQuery.data?.find((project) => project.id === selectedProjectId) || null,
    [projectsQuery.data, selectedProjectId],
  );
  const saveWorkspace = useSaveSolutionWorkspace(selectedProjectId);
  const generateSolution = useGenerateSolution(selectedProjectId);
  const extractRequirements = useExtractSolutionRequirements(selectedProjectId);
  const createTender = useCreateTenderFromSolution(selectedProjectId);
  const solutionFeedback = useSolutionFeedback(selectedProjectId);
  const outcome = useSolutionOutcome(selectedProjectId);
  const promoteTemplate = usePromoteSolutionTemplate(selectedProjectId);
  const versionsQuery = useSolutionVersions(selectedProjectId);

  useEffect(() => {
    if (selectedProject?.workspace) setWorkspace({ ...createSolutionWorkspace(), ...selectedProject.workspace });
  }, [selectedProject?.id, selectedProject?.workspace]);

  useEffect(() => {
    if (!selectedProjectId && !initialCustomerId && projectsQuery.data?.length) {
      setSearchParams({ project: projectsQuery.data[0].id }, { replace: true });
    }
  }, [initialCustomerId, projectsQuery.data, selectedProjectId, setSearchParams]);

  useEffect(() => {
    if (
      initialCustomerId
      && contextQuery.data
      && openedCustomerRef.current !== initialCustomerId
      && !selectedProjectId
    ) {
      openedCustomerRef.current = initialCustomerId;
      setCreateOpen(true);
    }
  }, [contextQuery.data, initialCustomerId, selectedProjectId]);

  const readiness = solutionReadiness(workspace);
  const completedStages = completedSolutionStages(workspace);
  const action = nextAction(workspace.active_stage, readiness);
  const activeStage = SOLUTION_STAGE_DEFINITIONS.find((stage) => stage.id === workspace.active_stage);
  const evidenceItems = useMemo<EvidenceDrawerItem[]>(() => {
    const documents = (contextQuery.data?.documents ?? []).map((document) => ({
      id: `document-${document.id}`,
      title: document.name,
      description: document.doc_type ? `企业资料 · ${document.doc_type}` : '企业资料',
      status: document.review_status === 'verified' ? 'verified' as const : 'pending' as const,
      source: document.source_version ? `资料版本 ${document.source_version}` : '企业知识库',
    }));
    const requirementEvidence = workspace.requirements
      .filter((requirement) => requirement.evidence_ref || requirement.status === 'open')
      .map((requirement) => ({
        id: `requirement-${requirement.id}`,
        title: requirement.title,
        description: requirement.source_excerpt || requirement.evidence_ref || '尚未绑定资料依据',
        status: requirement.status === 'verified' ? 'verified' as const : requirement.evidence_ref ? 'pending' as const : 'gap' as const,
        source: requirement.source_name || requirement.evidence_ref || undefined,
      }));
    return [...requirementEvidence, ...documents].slice(0, 40);
  }, [contextQuery.data?.documents, workspace.requirements]);

  const handleCreate = async (input: Parameters<typeof createProject.mutateAsync>[0]) => {
    const project = await createProject.mutateAsync(input);
    setSearchParams({ project: project.id });
    setWorkspace(project.workspace || createSolutionWorkspace(input));
    setCreateOpen(false);
    toast.success('客户方案已创建');
  };

  const handleSave = async () => {
    await saveWorkspace.mutateAsync(workspace);
    toast.success('方案进度已保存');
  };

  const handleGenerate = async () => {
    try {
      await saveWorkspace.mutateAsync(workspace);
      const result = await generateSolution.mutateAsync();
      if (result.cached) {
        toast.success(`输入与资料未变化，已复用第 ${result.version} 版，未产生新的模型费用`);
        return;
      }
      toast[result.degraded ? 'warning' : 'success'](
        result.degraded
          ? '模型服务暂时不可用，已生成可编辑的结构化兜底草稿'
          : `方案第 ${result.version} 版已生成，关键参数仍需人工核验`,
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '方案生成失败，请稍后重试');
    }
  };

  const handleExtract = async (documentIds: string[]) => {
    try {
      const result = await extractRequirements.mutateAsync({ document_ids: documentIds });
      if (result.project.workspace) setWorkspace(result.project.workspace);
      toast[result.degraded ? 'warning' : 'success'](
        result.degraded ? '已使用本地规则生成需求，请重点复核必选项' : `已提取 ${result.extracted_count} 条带来源需求`,
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '需求提取失败');
    }
  };

  const handleExport = async (format: 'markdown' | 'docx' | 'pdf' | 'xlsx') => {
    if (!selectedProjectId) return;
    try {
      await downloadSolution(selectedProjectId, format, selectedProject?.title);
      toast.success('交付文件已生成');
    } catch {
      toast.error('仍有未核验项，完成审校后再导出');
    }
  };

  const handleCreateTender = async () => {
    try {
      const tender = await createTender.mutateAsync();
      toast.success('已生成关联投标项目与应答矩阵');
      navigate(`/tender-analysis?project=${tender.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '转为投标项目失败');
    }
  };

  const handleFeedback = async (changeType: 'accepted' | 'edited' | 'rejected') => {
    await solutionFeedback.mutateAsync({ change_type: changeType });
    toast.success('本次反馈已进入方案学习样本');
  };

  const handleOutcome = async (input: Parameters<typeof outcome.mutateAsync>[0]) => {
    await outcome.mutateAsync(input);
    setWorkspace((current) => ({ ...current, extension_data: { ...current.extension_data, outcome: input } }));
    toast.success('业务结果已回流，将用于改进企业模板');
  };

  const handlePromoteTemplate = async () => {
    try {
      await promoteTemplate.mutateAsync();
      toast.success('已沉淀为企业方案模板');
    } catch {
      toast.error('方案通过审核或外发后才能沉淀为模板');
    }
  };

  const busy = saveWorkspace.isPending || generateSolution.isPending;
  return (
    <div className="mx-auto max-w-[1360px] space-y-5 pb-20" data-testid="solution-workspace">
      <header className="flex flex-col gap-4 border-b pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-medium text-primary"><FileStack className="h-4 w-4" />科学仪器方案作战</div>
          <h1 className="text-2xl font-semibold">客户解决方案工作台</h1>
          <p className="mt-1 text-sm text-muted-foreground">把客户需求、产品资料和历史经验组合成可核验、可编辑、可复用的方案。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select aria-label="选择方案项目" value={selectedProjectId || ''} onChange={(event) => setSearchParams(event.target.value ? { project: event.target.value } : {})} className="h-9 min-w-64 rounded-md border bg-background px-3 text-sm">
            {!projectsQuery.data?.length && <option value="">暂无方案项目</option>}
            {projectsQuery.data?.map((project) => <option key={project.id} value={project.id}>{project.title}</option>)}
          </select>
          <Button variant="outline" onClick={() => setCreateOpen(true)}><Plus className="mr-2 h-4 w-4" />新建方案</Button>
          <Button variant="outline" disabled={!selectedProjectId || busy} onClick={handleSave}>{saveWorkspace.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}保存</Button>
          <Button disabled={!selectedProjectId || busy} onClick={handleGenerate}>{generateSolution.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}{selectedProject?.current_version ? '生成新版' : '生成初稿'}</Button>
        </div>
      </header>

      {projectsQuery.isError && <div className="border-l-2 border-amber-500 bg-amber-50/60 px-4 py-3 text-sm text-amber-900">方案服务暂不可用。请确认最新数据库迁移已执行，再重试。</div>}

      <section className="grid grid-cols-2 border-y lg:grid-cols-4">
        {[
          { label: '当前项目', value: selectedProject?.title || '待创建', icon: FolderKanban },
          { label: '当前阶段', value: activeStage?.label || '客户简报', icon: BookOpenCheck },
          { label: '方案版本', value: `v${selectedProject?.current_version || 0}`, icon: FileStack },
          { label: '方案准备度', value: `${readiness.score}%`, icon: Gauge },
        ].map((metric) => <div key={metric.label} className="border-b p-4 odd:border-r [&:nth-child(n+3)]:border-b-0 lg:border-b-0 lg:border-r lg:last:border-r-0"><div className="flex items-center gap-2 text-xs text-muted-foreground"><metric.icon className="h-3.5 w-3.5" />{metric.label}</div><div className="mt-2 truncate text-sm font-semibold tabular-nums">{metric.value}</div></div>)}
      </section>

      {analyticsQuery.data && (
        <section className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b pb-3 text-xs text-muted-foreground" aria-label="方案价值指标">
          <span>团队方案 <strong className="text-foreground">{analyticsQuery.data.projects}</strong></span>
          <span>赢单率 <strong className="text-foreground">{analyticsQuery.data.win_rate}%</strong></span>
          <span>AI 采用率 <strong className="text-foreground">{analyticsQuery.data.acceptance_rate}%</strong></span>
          <span>累计 Token <strong className="text-foreground">{analyticsQuery.data.total_tokens.toLocaleString()}</strong></span>
          <span>估算成本 <strong className="text-foreground">${analyticsQuery.data.estimated_cost_usd.toFixed(4)}</strong></span>
        </section>
      )}

      <section className="flex flex-col gap-3 border-l-2 border-primary bg-primary/[0.035] px-4 py-3 md:flex-row md:items-center">
        <CheckCircle2 className="h-5 w-5 shrink-0 text-primary" />
        <div className="min-w-0 flex-1"><div className="text-sm font-semibold">{action[0]}</div><div className="text-xs text-muted-foreground">{action[1]}</div></div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{readiness.mustOpen} 项待核验</Badge>
          <EvidenceDrawer items={evidenceItems} title="方案依据与证据缺口" />
          <ContextAIActionMenu label="AI 辅助" actions={[
            { label: '补齐客户需求', prompt: `请协助补齐方案“${selectedProject?.title || workspace.brief.title || '当前方案'}”的客户事实。只询问行业、样品、检测目标、预算、地域、交付时间和约束条件中尚未明确的内容。` },
            { label: '检查资料缺口', prompt: `请检查方案“${selectedProject?.title || workspace.brief.title || '当前方案'}”的企业资料与证据缺口，只列出最影响产品选型和外发承诺的项目。` },
            { label: '审校当前方案', prompt: `请审校方案“${selectedProject?.title || workspace.brief.title || '当前方案'}”，重点检查参数依据、预算、地域适配、交付承诺和未经核验的表述。` },
          ]} />
        </div>
      </section>

      <SolutionStageRail activeStage={workspace.active_stage} completedStages={completedStages} onStageChange={(active_stage) => setWorkspace((current) => ({ ...current, active_stage }))} />

      <main className="min-h-[460px] border bg-background p-5 md:p-7">
        {!selectedProjectId && !projectsQuery.isLoading ? (
          <div className="flex min-h-[380px] flex-col items-center justify-center text-center"><FolderKanban className="h-8 w-8 text-muted-foreground" /><h2 className="mt-4 font-semibold">先建立第一个客户方案</h2><p className="mt-1 max-w-md text-sm text-muted-foreground">关联客户与应用场景后，系统会从企业知识资产和产品目录中检索依据。</p><Button className="mt-5" onClick={() => setCreateOpen(true)}><Plus className="mr-2 h-4 w-4" />新建客户方案</Button></div>
        ) : (
          <SolutionWorkspaceContent stage={workspace.active_stage} projectId={selectedProjectId || ''} workspace={workspace} versions={versionsQuery.data} documents={contextQuery.data?.documents} products={contextQuery.data?.products} canManageCatalog={contextQuery.data?.capabilities?.manage_catalog} canDeliver={contextQuery.data?.capabilities?.deliver_solution} isExtracting={extractRequirements.isPending} onChange={setWorkspace} onExtract={handleExtract} onExport={handleExport} onOutcome={handleOutcome} onPromoteTemplate={handlePromoteTemplate} onCreateTender={handleCreateTender} onFeedback={handleFeedback} />
        )}
      </main>

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t pt-4 text-xs text-muted-foreground"><span>AI 只在主动生成或重构时调用；编辑、校验和导出不消耗对话模型。</span><span>{workspace.generation.model ? `最近生成：${workspace.generation.model}${workspace.generation.duration_ms ? ` · ${(workspace.generation.duration_ms / 1000).toFixed(1)} 秒` : ''}` : '尚未生成 AI 草稿'}</span></footer>
      <SolutionProjectDialog
        open={createOpen}
        options={contextQuery.data}
        initialCustomerId={initialCustomerId}
        isSubmitting={createProject.isPending}
        onOpenChange={setCreateOpen}
        onSubmit={handleCreate}
      />
    </div>
  );
}
