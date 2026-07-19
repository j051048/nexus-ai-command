import { Check, FileDown, Plus, Sparkles, Trash2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { SCIENTIFIC_INSTRUMENT_LINES } from '@/config/growthOperatingModel';

import type {
  SolutionBrief,
  SolutionPackage,
  SolutionRequirement,
  SolutionVersionSummary,
  SolutionWorkspaceState,
} from './types';
import { solutionReadiness } from './workspaceModel';

interface BasePanelProps {
  workspace: SolutionWorkspaceState;
  onChange: (workspace: SolutionWorkspaceState) => void;
}

export function BriefPanel({ workspace, onChange }: BasePanelProps) {
  const brief = workspace.brief;
  const update = <K extends keyof SolutionBrief>(key: K, value: SolutionBrief[K]) =>
    onChange({ ...workspace, brief: { ...brief, [key]: value } });
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
      <section className="grid gap-4 md:grid-cols-2">
        <label className="space-y-1.5 text-sm font-medium md:col-span-2">方案名称<Input value={brief.title} onChange={(event) => update('title', event.target.value)} /></label>
        <label className="space-y-1.5 text-sm font-medium">客户名称<Input value={brief.customer_name || ''} onChange={(event) => update('customer_name', event.target.value)} /></label>
        <label className="space-y-1.5 text-sm font-medium">行业<Input value={brief.industry || ''} onChange={(event) => update('industry', event.target.value)} /></label>
        <label className="space-y-1.5 text-sm font-medium">地区<Input value={brief.region || ''} onChange={(event) => update('region', event.target.value)} /></label>
        <label className="space-y-1.5 text-sm font-medium">仪器谱系<select value={brief.instrument_line_code || ''} onChange={(event) => update('instrument_line_code', event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm"><option value="">待确认</option>{SCIENTIFIC_INSTRUMENT_LINES.map((line) => <option key={line.code} value={line.code}>{line.name}</option>)}</select></label>
        <label className="space-y-1.5 text-sm font-medium">最低预算<Input type="number" value={brief.budget_min ?? ''} onChange={(event) => update('budget_min', event.target.value ? Number(event.target.value) : undefined)} /></label>
        <label className="space-y-1.5 text-sm font-medium">最高预算<Input type="number" value={brief.budget_max ?? ''} onChange={(event) => update('budget_max', event.target.value ? Number(event.target.value) : undefined)} /></label>
        <label className="space-y-1.5 text-sm font-medium md:col-span-2">应用场景与客户目标<Textarea className="min-h-36" value={brief.application_scenario || ''} onChange={(event) => update('application_scenario', event.target.value)} /></label>
      </section>
      <aside className="border-l pl-5 text-sm">
        <h3 className="font-medium">建议补齐的事实</h3>
        <ul className="mt-3 space-y-3 text-muted-foreground">
          <li>样品类型、目标指标与日均通量</li><li>现有设备、安装环境与操作人员</li><li>预算来源、采购时间与验收方式</li><li>客户明确关注的竞品或型号</li>
        </ul>
      </aside>
    </div>
  );
}

export function RequirementsPanel({ workspace, onChange }: BasePanelProps) {
  const updateItem = (index: number, patch: Partial<SolutionRequirement>) => onChange({ ...workspace, requirements: workspace.requirements.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) });
  const addItem = () => onChange({ ...workspace, requirements: [...workspace.requirements, { id: `req-${Date.now()}`, title: '', priority: 'should', status: 'open', evidence_ref: null }] });
  return (
    <section>
      <div className="mb-4 flex items-center justify-between"><div><h2 className="font-semibold">需求与证据</h2><p className="text-sm text-muted-foreground">必选需求需要证据来源，不能只标记“已确认”。</p></div><Button variant="outline" size="sm" onClick={addItem}><Plus className="mr-2 h-4 w-4" />添加需求</Button></div>
      <div className="divide-y border-y">
        {workspace.requirements.map((item, index) => (
          <div key={item.id} className="grid gap-3 py-4 md:grid-cols-[110px_minmax(0,1fr)_180px_120px_36px] md:items-center">
            <select value={item.priority} onChange={(event) => updateItem(index, { priority: event.target.value as SolutionRequirement['priority'] })} className="h-9 rounded-md border bg-background px-2 text-sm"><option value="must">必选</option><option value="should">建议</option><option value="optional">可选</option></select>
            <Input value={item.title} onChange={(event) => updateItem(index, { title: event.target.value })} placeholder="客户要求或设计约束" />
            <Input value={item.evidence_ref || ''} onChange={(event) => updateItem(index, { evidence_ref: event.target.value })} placeholder="资料名称 / 页码" />
            <select value={item.status} onChange={(event) => updateItem(index, { status: event.target.value as SolutionRequirement['status'] })} className="h-9 rounded-md border bg-background px-2 text-sm"><option value="open">待核验</option><option value="verified">已核验</option><option value="excluded">不适用</option></select>
            <Button variant="ghost" size="icon" title="删除需求" onClick={() => onChange({ ...workspace, requirements: workspace.requirements.filter((_, itemIndex) => itemIndex !== index) })}><Trash2 className="h-4 w-4" /></Button>
          </div>
        ))}
        {!workspace.requirements.length && <div className="py-14 text-center text-sm text-muted-foreground">尚未生成或录入需求。可先让 AI 基于客户简报和知识库生成第一版。</div>}
      </div>
    </section>
  );
}

function PackageColumn({ item, onChange }: { item: SolutionPackage; onChange: (item: SolutionPackage) => void }) {
  return (
    <article className="border-l px-4 first:border-l-0">
      <Input value={item.name} onChange={(event) => onChange({ ...item, name: event.target.value })} className="font-semibold" />
      <Textarea value={item.positioning} onChange={(event) => onChange({ ...item, positioning: event.target.value })} className="mt-3 min-h-20" placeholder="方案定位" />
      <label className="mt-4 block text-xs font-medium text-muted-foreground">产品型号（每行一个）</label>
      <Textarea value={item.product_models.join('\n')} onChange={(event) => onChange({ ...item, product_models: event.target.value.split('\n').filter(Boolean) })} className="mt-1 min-h-24" />
      <label className="mt-4 block text-xs font-medium text-muted-foreground">配置与服务（每行一个）</label>
      <Textarea value={item.components.join('\n')} onChange={(event) => onChange({ ...item, components: event.target.value.split('\n').filter(Boolean) })} className="mt-1 min-h-32" />
      <label className="mt-4 block text-xs font-medium text-muted-foreground">推荐理由</label>
      <Textarea value={item.rationale} onChange={(event) => onChange({ ...item, rationale: event.target.value })} className="mt-1 min-h-24" />
    </article>
  );
}

export function ConfigurationPanel({ workspace, onChange }: BasePanelProps) {
  return (
    <section>
      <div className="mb-4"><h2 className="font-semibold">三档配置建议</h2><p className="text-sm text-muted-foreground">同一需求给出基础、推荐、进阶三种取舍，价格与参数仍需人工核对。</p></div>
      {workspace.packages.length ? <div className="grid border-y py-4 lg:grid-cols-3">{workspace.packages.slice(0, 3).map((item, index) => <PackageColumn key={item.id} item={item} onChange={(next) => onChange({ ...workspace, packages: workspace.packages.map((current, itemIndex) => itemIndex === index ? next : current) })} />)}</div> : <div className="border-y py-16 text-center text-sm text-muted-foreground"><Sparkles className="mx-auto mb-3 h-6 w-6" />生成方案后，这里会出现基础、推荐和进阶三档配置。</div>}
    </section>
  );
}

export function DraftPanel({ workspace, onChange }: BasePanelProps) {
  return (
    <section className="space-y-4">
      <div><h2 className="font-semibold">方案章节</h2><p className="text-sm text-muted-foreground">编辑结论，并明确每段使用了哪些企业资料。</p></div>
      {workspace.sections.map((section, index) => (
        <article key={section.id} className="border-b pb-5">
          <div className="flex items-center gap-2"><Input value={section.title} onChange={(event) => onChange({ ...workspace, sections: workspace.sections.map((item, itemIndex) => itemIndex === index ? { ...item, title: event.target.value } : item) })} className="font-semibold" /><Button variant={section.status === 'approved' ? 'default' : 'outline'} size="sm" onClick={() => onChange({ ...workspace, sections: workspace.sections.map((item, itemIndex) => itemIndex === index ? { ...item, status: item.status === 'approved' ? 'review' : 'approved' } : item) })}>{section.status === 'approved' && <Check className="mr-1 h-3.5 w-3.5" />}{section.status === 'approved' ? '已批准' : '批准本段'}</Button></div>
          <Textarea value={section.content} onChange={(event) => onChange({ ...workspace, sections: workspace.sections.map((item, itemIndex) => itemIndex === index ? { ...item, content: event.target.value } : item) })} className="mt-3 min-h-40 leading-6" />
          <Input value={section.evidence_refs.join('；')} onChange={(event) => onChange({ ...workspace, sections: workspace.sections.map((item, itemIndex) => itemIndex === index ? { ...item, evidence_refs: event.target.value.split(/[；;]/).map((value) => value.trim()).filter(Boolean) } : item) })} className="mt-2" placeholder="证据引用：产品手册第 12 页；历史方案 A" />
        </article>
      ))}
      {!workspace.sections.length && <div className="border-y py-16 text-center text-sm text-muted-foreground">当前没有章节草稿。</div>}
    </section>
  );
}

export function ReviewPanel({ workspace, onChange }: BasePanelProps) {
  const readiness = solutionReadiness(workspace);
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
      <section><h2 className="font-semibold">外发前人工门禁</h2><div className="mt-4 divide-y border-y">{workspace.review_gates.map((gate, index) => <label key={gate.id} className="flex cursor-pointer items-center gap-3 py-4"><input type="checkbox" checked={gate.passed} onChange={(event) => onChange({ ...workspace, review_gates: workspace.review_gates.map((item, itemIndex) => itemIndex === index ? { ...item, passed: event.target.checked } : item) })} className="h-4 w-4" /><span className="text-sm font-medium">{gate.label}</span><Badge variant={gate.passed ? 'default' : 'outline'} className="ml-auto">{gate.passed ? '已确认' : '待确认'}</Badge></label>)}</div></section>
      <aside className="border-l pl-5"><h3 className="font-medium">质量摘要</h3><dl className="mt-4 space-y-3 text-sm"><div className="flex justify-between"><dt className="text-muted-foreground">方案准备度</dt><dd className="font-semibold">{readiness.score}%</dd></div><div className="flex justify-between"><dt className="text-muted-foreground">待核验必选项</dt><dd>{readiness.mustOpen}</dd></div><div className="flex justify-between"><dt className="text-muted-foreground">证据引用</dt><dd>{readiness.evidenceCount}</dd></div><div className="flex justify-between"><dt className="text-muted-foreground">已批准章节</dt><dd>{readiness.approvedSections}</dd></div></dl><p className="mt-5 text-xs leading-5 text-muted-foreground">系统不会自动对外发送。只有证据、预算和承诺全部通过人工门禁后才开放导出。</p></aside>
    </div>
  );
}

interface DeliveryPanelProps extends BasePanelProps {
  projectId: string;
  versions?: SolutionVersionSummary[];
  onExport: (format: 'markdown' | 'docx' | 'pdf') => Promise<void>;
  onOutcome: (input: { outcome_type: 'proposal' | 'won' | 'lost' | 'revenue' | 'time_saved'; amount?: number; note?: string }) => Promise<void>;
  onPromoteTemplate: () => Promise<void>;
}

export function DeliveryPanel({ workspace, projectId, versions = [], onExport, onOutcome, onPromoteTemplate }: DeliveryPanelProps) {
  const readiness = solutionReadiness(workspace);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section><h2 className="font-semibold">导出交付物</h2><p className="mt-1 text-sm text-muted-foreground">导出不会再次调用 AI，也不会自动发送给客户。</p><div className="mt-5 flex flex-wrap gap-2">{(['docx', 'pdf', 'markdown'] as const).map((format) => <Button key={format} variant={format === 'docx' ? 'default' : 'outline'} disabled={!projectId || !readiness.canExport} onClick={() => onExport(format)}><FileDown className="mr-2 h-4 w-4" />{format.toUpperCase()}</Button>)}</div>{!readiness.canExport && <p className="mt-3 text-xs text-amber-700">请先核验必选需求、补齐证据、批准全部章节并完成三项人工门禁。</p>}</section>
      <section className="border-l pl-6"><h2 className="font-semibold">结果回流</h2><p className="mt-1 text-sm text-muted-foreground">记录方案是否外发、赢单或节省工时，用真实结果改进模板。</p><div className="mt-5 flex flex-wrap gap-2"><Button variant="outline" onClick={() => onOutcome({ outcome_type: 'proposal' })}>已发送客户</Button><Button variant="outline" onClick={() => onOutcome({ outcome_type: 'won' })}>赢单</Button><Button variant="outline" onClick={() => onOutcome({ outcome_type: 'lost' })}>丢单</Button><Button variant="outline" onClick={() => onOutcome({ outcome_type: 'time_saved', amount: 8, note: '方案生成与整理预计节省工时' })}>记录节省 8 小时</Button></div><Button className="mt-4" variant="secondary" onClick={onPromoteTemplate}>沉淀为企业模板</Button></section>
      <section className="border-t pt-5 lg:col-span-2"><h2 className="font-semibold">版本记录</h2><p className="mt-1 text-sm text-muted-foreground">每次 AI 生成都会保留独立版本，方便审计模型、时间与降级状态。</p><div className="mt-4 divide-y border-y">{versions.map((version) => <div key={version.id} className="flex flex-wrap items-center gap-3 py-3 text-sm"><span className="font-medium">v{version.version_number}</span><span className="min-w-0 flex-1 truncate">{version.title}</span><Badge variant="outline">{version.generation_metadata?.degraded ? '兜底草稿' : version.generation_metadata?.model || '模型未记录'}</Badge>{version.created_at && <time className="text-xs text-muted-foreground">{new Date(version.created_at).toLocaleString('zh-CN')}</time>}</div>)}{!versions.length && <div className="py-8 text-center text-sm text-muted-foreground">生成第一版方案后，版本记录会出现在这里。</div>}</div></section>
    </div>
  );
}
