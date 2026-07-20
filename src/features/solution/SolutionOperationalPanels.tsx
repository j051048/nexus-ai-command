import { AlertTriangle, Calculator, Check, FileCheck2, MessageSquarePlus, Send, Sparkles } from 'lucide-react';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';

import type { SolutionEvaluation, SolutionVersionSummary, SolutionWorkspaceState } from './types';
import {
  useCommercialApprovals,
  useCreateSolutionComment,
  useDeliverSolution,
  useRequestCommercialApproval,
  useRewriteSolutionSection,
  useSolutionComments,
  useSolutionConnectors,
  useSolutionCPQ,
  useSolutionEvaluation,
  useSolutionVersionDetail,
  useTenderReadiness,
} from './useSolutionWorkspace';

export function SolutionCPQWorkbench({
  projectId,
  workspace,
  onChange,
}: {
  projectId: string;
  workspace: SolutionWorkspaceState;
  onChange: (workspace: SolutionWorkspaceState) => void;
}) {
  const cpq = useSolutionCPQ(projectId || null);
  const approvals = useCommercialApprovals(projectId || null);
  const requestApproval = useRequestCommercialApproval(projectId || null);
  const [taxRate, setTaxRate] = useState(0.13);
  const calculate = async () => {
    try {
      const result = await cpq.mutateAsync({ workspace, tax_rate: taxRate });
      onChange({
        ...workspace,
        packages: workspace.packages.map((item) => {
          const quote = result.quotes.find((candidate) => candidate.package_id === item.id);
          return quote ? { ...item, commercial: { ...item.commercial, ...quote } } : item;
        }),
        extension_data: { ...workspace.extension_data, cpq: result },
      });
      toast[result.valid ? 'success' : 'warning'](result.valid ? '报价核算已完成' : '报价存在待核验项');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '报价核算失败');
    }
  };
  const recommendedPackage = workspace.packages.find((item) => item.id === 'recommended');
  const recommendedQuote = cpq.data?.quotes.find((item) => item.package_id === 'recommended');
  const recommended = recommendedQuote || recommendedPackage?.commercial;
  const approval = approvals.data?.find((item) => item.package_id === 'recommended');
  const submitApproval = async () => {
    if (!recommended?.approval_required) return;
    try {
      await requestApproval.mutateAsync({
        package_id: 'recommended',
        workspace,
        tax_rate: taxRate,
        reason: recommended.approval_reasons?.join('；') || '报价超出企业授权范围',
      });
      toast.success('商业例外已提交审批');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '提交商业审批失败');
    }
  };
  return (
    <section className="mb-5 border-y bg-muted/20 px-4 py-3" aria-label="科学仪器报价核算">
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <Calculator className="h-4 w-4 text-primary" />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold">报价核算</h3>
          <p className="text-xs text-muted-foreground">按数量、折扣、区域价格与税率计算；超授权范围自动进入审批。</p>
        </div>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          税率
          <Input className="h-8 w-20" type="number" min={0} max={1} step={0.01} value={taxRate} onChange={(event) => setTaxRate(Number(event.target.value) || 0)} />
        </label>
        <Button size="sm" variant="outline" disabled={!projectId || cpq.isPending} onClick={calculate}>
          {cpq.isPending ? '核算中' : '重新核算'}
        </Button>
      </div>
      {recommended?.total != null && (
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 border-t pt-3 text-xs">
          <span>推荐方案含税价 <strong className="ml-1 tabular-nums">{recommended.currency || 'CNY'} {recommended.total.toLocaleString()}</strong></span>
          {recommended.gross_margin_percent != null && <span>毛利率 <strong className="ml-1 tabular-nums">{recommended.gross_margin_percent}%</strong></span>}
          <span>交期 <strong className="ml-1">{recommended.lead_time_days || '待确认'} 天</strong></span>
          {recommended.approval_required && (
            approval?.status === 'approved'
              ? <Badge variant="outline" className="border-emerald-300 text-emerald-700">商业例外已批准</Badge>
              : approval?.status === 'pending'
                ? <Badge variant="outline" className="border-amber-300 text-amber-700">商业审批处理中</Badge>
                : <Button size="sm" variant="outline" disabled={requestApproval.isPending} onClick={submitApproval}>提交商业审批</Button>
          )}
        </div>
      )}
    </section>
  );
}

export function SolutionConnectorDelivery({
  projectId,
  canDeliver,
}: {
  projectId: string;
  canDeliver: boolean;
}) {
  const connectors = useSolutionConnectors(canDeliver);
  const delivery = useDeliverSolution(projectId || null);
  const { confirm, ConfirmDialog } = useConfirmDialog();
  const [selectedCode, setSelectedCode] = useState('');
  const activeConnectors = (connectors.data || []).filter(
    (item) => item.status === 'active' && item.capabilities.includes('solution.delivery'),
  );
  const connectorCode = selectedCode || activeConnectors[0]?.connector_code || '';
  if (!canDeliver) return null;

  const deliver = async () => {
    const connector = activeConnectors.find((item) => item.connector_code === connectorCode);
    if (!connector) return;
    const accepted = await confirm({
      title: '确认交付方案',
      description: `方案将发送到“${connector.display_name}”。这是对外操作，发送后可能触发企业系统中的后续流程。`,
      confirmText: '确认发送',
    });
    if (!accepted) return;
    try {
      const requestKey = typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      await delivery.mutateAsync({ connector_code: connectorCode, request_key: requestKey });
      toast.success(`方案已交付到 ${connector.display_name}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '连接器交付失败');
    }
  };

  return (
    <section className="border-t pt-5 lg:col-span-2">
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <Send className="h-4 w-4 text-primary" />
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold">交付到企业系统</h2>
          <p className="text-xs text-muted-foreground">仅显示管理员已启用的连接器；每次交付都有幂等键和审计记录。</p>
        </div>
        {activeConnectors.length ? (
          <>
            <select
              aria-label="选择交付连接器"
              className="h-9 min-w-48 rounded-md border bg-background px-3 text-sm"
              value={connectorCode}
              onChange={(event) => setSelectedCode(event.target.value)}
            >
              {activeConnectors.map((item) => <option key={item.connector_code} value={item.connector_code}>{item.display_name}</option>)}
            </select>
            <Button size="sm" disabled={!projectId || delivery.isPending} onClick={deliver}>
              <Send className="mr-2 h-4 w-4" />{delivery.isPending ? '发送中' : '确认并发送'}
            </Button>
          </>
        ) : <span className="text-xs text-muted-foreground">尚无已启用连接器</span>}
      </div>
      {ConfirmDialog}
    </section>
  );
}

export function SolutionSectionWorkbench({
  projectId,
  workspace,
  onChange,
}: {
  projectId: string;
  workspace: SolutionWorkspaceState;
  onChange: (workspace: SolutionWorkspaceState) => void;
}) {
  const [selectedId, setSelectedId] = useState(workspace.sections[0]?.id || '');
  const [comment, setComment] = useState('');
  const [candidate, setCandidate] = useState<string | null>(null);
  const comments = useSolutionComments(projectId || null);
  const createComment = useCreateSolutionComment(projectId || null);
  const rewrite = useRewriteSolutionSection(projectId || null);
  const selected = workspace.sections.find((item) => item.id === selectedId) || workspace.sections[0];
  const sectionComments = useMemo(
    () => comments.data?.filter((item) => item.section_id === selected?.id && item.status === 'open') || [],
    [comments.data, selected?.id],
  );
  if (!selected) return null;

  const requestRewrite = async (mode: 'concise' | 'technical' | 'executive' | 'proofread') => {
    try {
      const result = await rewrite.mutateAsync({ section_id: selected.id, mode });
      setCandidate(result.revised_content);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '章节改写失败');
    }
  };
  const applyCandidate = () => {
    if (!candidate) return;
    onChange({
      ...workspace,
      sections: workspace.sections.map((item) => item.id === selected.id ? { ...item, content: candidate, status: 'review' } : item),
    });
    setCandidate(null);
    toast.success('改写内容已应用，保存后生效');
  };
  return (
    <div className="grid gap-5 lg:grid-cols-[210px_minmax(0,1fr)_260px]">
      <nav className="border-r pr-3" aria-label="方案章节目录">
        <div className="mb-2 text-xs font-medium text-muted-foreground">章节目录</div>
        {workspace.sections.map((item, index) => (
          <button key={item.id} type="button" onClick={() => { setSelectedId(item.id); setCandidate(null); }} className={`flex w-full items-center gap-2 border-l-2 px-3 py-2 text-left text-sm ${item.id === selected.id ? 'border-primary bg-primary/[0.04] font-medium' : 'border-transparent text-muted-foreground'}`}>
            <span className="w-5 tabular-nums">{index + 1}</span><span className="truncate">{item.title}</span>
          </button>
        ))}
      </nav>
      <section>
        <div className="flex flex-wrap items-center gap-2 border-b pb-3">
          <h3 className="min-w-0 flex-1 truncate font-semibold">{selected.title}</h3>
          <Button size="sm" variant="ghost" disabled={rewrite.isPending} onClick={() => requestRewrite('concise')}>精简</Button>
          <Button size="sm" variant="ghost" disabled={rewrite.isPending} onClick={() => requestRewrite('technical')}>技术化</Button>
          <Button size="sm" variant="ghost" disabled={rewrite.isPending} onClick={() => requestRewrite('executive')}><Sparkles className="mr-1 h-3.5 w-3.5" />管理层版</Button>
        </div>
        <textarea
          className="mt-3 min-h-72 w-full resize-y border-0 bg-transparent p-0 text-sm leading-7 outline-none"
          value={selected.content}
          onChange={(event) => onChange({ ...workspace, sections: workspace.sections.map((item) => item.id === selected.id ? { ...item, content: event.target.value, status: 'review' } : item) })}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          {selected.evidence_refs.map((reference) => <Badge key={reference} variant="outline">{reference}</Badge>)}
          {!selected.evidence_refs.length && <span className="flex items-center gap-1 text-xs text-amber-700"><AlertTriangle className="h-3.5 w-3.5" />本章暂无证据引用</span>}
        </div>
        {candidate && (
          <div className="mt-4 border-l-2 border-primary bg-primary/[0.035] p-4">
            <div className="flex items-center justify-between"><strong className="text-sm">AI 改写建议</strong><span className="text-xs text-muted-foreground">尚未写入方案</span></div>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{candidate}</p>
            <div className="mt-4 flex gap-2"><Button size="sm" onClick={applyCandidate}><Check className="mr-1 h-3.5 w-3.5" />应用建议</Button><Button size="sm" variant="outline" onClick={() => setCandidate(null)}>放弃</Button></div>
          </div>
        )}
      </section>
      <aside className="border-l pl-4">
        <h3 className="flex items-center gap-2 text-sm font-semibold"><MessageSquarePlus className="h-4 w-4" />评审意见</h3>
        <div className="mt-3 space-y-2">
          {sectionComments.map((item) => <div key={item.id} className="border-l-2 pl-3 text-xs leading-5">{item.content}</div>)}
          {!sectionComments.length && <p className="text-xs text-muted-foreground">本章暂无待处理意见</p>}
        </div>
        <Input className="mt-4" value={comment} onChange={(event) => setComment(event.target.value)} placeholder="添加评审意见" />
        <Button className="mt-2" size="sm" variant="outline" disabled={!comment.trim() || createComment.isPending} onClick={async () => { await createComment.mutateAsync({ section_id: selected.id, content: comment.trim() }); setComment(''); }}>添加意见</Button>
      </aside>
    </div>
  );
}

export function SolutionQualityPanel({ projectId }: { projectId: string }) {
  const evaluation = useSolutionEvaluation(projectId || null);
  const [result, setResult] = useState<SolutionEvaluation | null>(null);
  return (
    <section className="mb-5 border-y px-4 py-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <FileCheck2 className="h-4 w-4 text-primary" />
        <div className="min-w-0 flex-1"><h3 className="text-sm font-semibold">方案质量评测</h3><p className="text-xs text-muted-foreground">确定性检查需求、证据、商业完整性、兼容性与承诺风险，不消耗 Token。</p></div>
        <Button size="sm" variant="outline" disabled={!projectId || evaluation.isPending} onClick={async () => setResult(await evaluation.mutateAsync())}>{evaluation.isPending ? '评测中' : '运行评测'}</Button>
      </div>
      {result && <div className="mt-3 flex flex-wrap items-center gap-4 border-t pt-3 text-xs"><strong className="text-base tabular-nums">{result.score} 分</strong><Badge variant={result.ready ? 'default' : 'outline'}>{result.ready ? '可进入交付审核' : '仍需修订'}</Badge>{result.findings.slice(0, 3).map((item) => <span key={item.code} className="text-amber-700">{item.message}</span>)}</div>}
    </section>
  );
}

export function TenderReadinessPanel({ projectId }: { projectId: string }) {
  const readiness = useTenderReadiness(projectId || null);
  if (!readiness.data) return null;
  const decisionLabel = { bid: '建议参与', review: '需评审', no_bid: '建议放弃' }[readiness.data.decision];
  return (
    <section className="mt-5 border-y py-4">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        <strong>Bid / No-Bid</strong>
        <Badge variant={readiness.data.decision === 'bid' ? 'default' : 'outline'}>{decisionLabel}</Badge>
        <span className="text-muted-foreground">就绪度 <strong className="text-foreground">{readiness.data.score}</strong></span>
        <span className="text-muted-foreground">需求覆盖 <strong className="text-foreground">{readiness.data.coverage_percent}%</strong></span>
        <span className="text-muted-foreground">重大偏差 <strong className="text-foreground">{readiness.data.major_deviations}</strong></span>
      </div>
    </section>
  );
}

export function SolutionVersionCompare({
  projectId,
  workspace,
  versions,
}: {
  projectId: string;
  workspace: SolutionWorkspaceState;
  versions: SolutionVersionSummary[];
}) {
  const [versionNumber, setVersionNumber] = useState<number | null>(versions[1]?.version_number || versions[0]?.version_number || null);
  const detail = useSolutionVersionDetail(projectId || null, versionNumber);
  const previousSections = detail.data?.content?.sections || [];
  const changed = workspace.sections.filter((section) => {
    const previous = previousSections.find((item) => item.id === section.id);
    return !previous || previous.title !== section.title || previous.content !== section.content;
  }).length;
  if (!versions.length) return null;
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3 border-y py-3 text-xs">
      <strong>版本对比</strong>
      <select className="h-8 rounded-md border bg-background px-2" value={versionNumber || ''} onChange={(event) => setVersionNumber(Number(event.target.value) || null)}>
        {versions.map((version) => <option key={version.id} value={version.version_number}>v{version.version_number} · {version.title}</option>)}
      </select>
      {detail.data && <span className="text-muted-foreground">与当前编辑稿相比，<strong className="text-foreground">{changed}</strong> 个章节发生变化</span>}
    </div>
  );
}
