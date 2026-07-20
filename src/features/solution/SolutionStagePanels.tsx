import { AlertTriangle, FileDown, FileSearch, Gavel, Plus, Sparkles, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { SCIENTIFIC_INSTRUMENT_LINES } from '@/config/growthOperatingModel';

import { ProductCatalogManager } from './ProductCatalogManager';
import {
  SolutionCPQWorkbench,
  SolutionConnectorDelivery,
  SolutionQualityPanel,
  SolutionSectionWorkbench,
  SolutionVersionCompare,
  TenderReadinessPanel,
} from './SolutionOperationalPanels';
import type {
  SolutionBrief,
  SolutionDocumentOption,
  SolutionPackage,
  SolutionProductOption,
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

interface RequirementsPanelProps extends BasePanelProps {
  documents?: SolutionDocumentOption[];
  isExtracting?: boolean;
  onExtract?: (documentIds: string[]) => Promise<void>;
}

export function RequirementsPanel({ workspace, onChange, documents = [], isExtracting, onExtract }: RequirementsPanelProps) {
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>(
    () => ((workspace.extension_data.source_documents as Array<{ id?: string }> | undefined) || [])
      .map((item) => item.id || '')
      .filter(Boolean),
  );
  const updateItem = (index: number, patch: Partial<SolutionRequirement>) => onChange({ ...workspace, requirements: workspace.requirements.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) });
  const addItem = () => onChange({ ...workspace, requirements: [...workspace.requirements, { id: `req-${Date.now()}`, title: '', priority: 'should', status: 'open', evidence_ref: null }] });
  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 border-b pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div><h2 className="font-semibold">需求与证据</h2><p className="text-sm text-muted-foreground">先选择招标文件、技术协议或客户资料，再生成可追溯的需求矩阵。</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <details className="relative">
            <summary className="flex h-9 cursor-pointer list-none items-center rounded-md border bg-background px-3 text-sm">已选 {selectedDocuments.length} 份资料</summary>
            <div className="absolute right-0 z-20 mt-1 max-h-72 w-80 overflow-auto rounded-md border bg-popover p-2 shadow-md">
              {documents.map((document) => (
                <label key={document.id} className="flex cursor-pointer items-start gap-2 rounded px-2 py-2 text-sm hover:bg-accent">
                  <input
                    type="checkbox"
                    className="mt-0.5 h-4 w-4"
                    checked={selectedDocuments.includes(document.id)}
                    onChange={(event) => setSelectedDocuments((current) => event.target.checked ? [...current, document.id] : current.filter((id) => id !== document.id))}
                  />
                  <span className="min-w-0 flex-1"><span className="block truncate font-medium">{document.name}</span><span className="text-xs text-muted-foreground">{document.doc_type || '未分类'} · {document.review_status === 'verified' ? '已审核' : '待审核'}</span></span>
                </label>
              ))}
              {!documents.length && <p className="px-2 py-6 text-center text-xs text-muted-foreground">请先在企业知识库上传并索引资料</p>}
            </div>
          </details>
          <Button size="sm" disabled={!selectedDocuments.length || isExtracting} onClick={() => onExtract?.(selectedDocuments)}><FileSearch className="mr-2 h-4 w-4" />{isExtracting ? '提取中' : '提取需求'}</Button>
          <Button variant="outline" size="sm" onClick={addItem}><Plus className="mr-2 h-4 w-4" />手工添加</Button>
        </div>
      </div>
      <div className="divide-y border-y">
        {workspace.requirements.map((item, index) => (
          <div key={item.id} className="grid gap-3 py-4 md:grid-cols-[110px_minmax(0,1fr)_180px_120px_36px] md:items-center">
            <select value={item.priority} onChange={(event) => updateItem(index, { priority: event.target.value as SolutionRequirement['priority'] })} className="h-9 rounded-md border bg-background px-2 text-sm"><option value="must">必选</option><option value="should">建议</option><option value="optional">可选</option></select>
            <Input value={item.title} onChange={(event) => updateItem(index, { title: event.target.value })} placeholder="客户要求或设计约束" />
            <div className="min-w-0"><Input value={item.evidence_ref || ''} onChange={(event) => updateItem(index, { evidence_ref: event.target.value })} placeholder="资料 ID / 页码" />{item.source_name && <p className="mt-1 truncate text-xs text-muted-foreground" title={item.source_excerpt || ''}>{item.source_name}</p>}</div>
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
  const commercial = item.commercial;
  const lineItems = item.line_items?.length
    ? item.line_items
    : item.product_models.map((model_code) => ({ model_code, quantity: 1, discount_percent: 0 }));
  const updateModels = (value: string) => {
    const product_models = value.split('\n').map((model) => model.trim()).filter(Boolean);
    onChange({
      ...item,
      product_models,
      line_items: product_models.map((model_code) => lineItems.find((line) => line.model_code === model_code) || { model_code, quantity: 1, discount_percent: 0 }),
    });
  };
  return (
    <article className="border-l px-4 first:border-l-0">
      <Input value={item.name} onChange={(event) => onChange({ ...item, name: event.target.value })} className="font-semibold" />
      <Textarea value={item.positioning} onChange={(event) => onChange({ ...item, positioning: event.target.value })} className="mt-3 min-h-20" placeholder="方案定位" />
      <label className="mt-4 block text-xs font-medium text-muted-foreground">产品型号（每行一个）</label>
      <Textarea value={item.product_models.join('\n')} onChange={(event) => updateModels(event.target.value)} className="mt-1 min-h-24" />
      {!!lineItems.length && <div className="mt-2 divide-y border-y">{lineItems.map((line, lineIndex) => <div key={`${line.model_code}-${lineIndex}`} className="grid grid-cols-[minmax(0,1fr)_56px_64px] items-center gap-2 py-2 text-xs"><span className="truncate font-medium">{line.model_code}</span><Input aria-label={`${line.model_code} 数量`} title="数量" className="h-7 px-2" type="number" min={1} value={line.quantity} onChange={(event) => onChange({ ...item, line_items: lineItems.map((current, index) => index === lineIndex ? { ...current, quantity: Math.max(1, Number(event.target.value) || 1) } : current) })} /><Input aria-label={`${line.model_code} 折扣`} title="折扣百分比" className="h-7 px-2" type="number" min={0} max={100} value={line.discount_percent || 0} onChange={(event) => onChange({ ...item, line_items: lineItems.map((current, index) => index === lineIndex ? { ...current, discount_percent: Math.max(0, Math.min(100, Number(event.target.value) || 0)) } : current) })} /></div>)}</div>}
      <label className="mt-4 block text-xs font-medium text-muted-foreground">配置与服务（每行一个）</label>
      <Textarea value={item.components.join('\n')} onChange={(event) => onChange({ ...item, components: event.target.value.split('\n').filter(Boolean) })} className="mt-1 min-h-32" />
      <label className="mt-4 block text-xs font-medium text-muted-foreground">推荐理由</label>
      <Textarea value={item.rationale} onChange={(event) => onChange({ ...item, rationale: event.target.value })} className="mt-1 min-h-24" />
      {commercial && (
        <div className="mt-4 border-t pt-3 text-xs">
          <div className="grid grid-cols-2 gap-2"><span className="text-muted-foreground">目录价</span><strong className="text-right tabular-nums">{commercial.list_price == null ? '待核价' : `${commercial.currency || 'CNY'} ${commercial.list_price.toLocaleString()}`}</strong><span className="text-muted-foreground">毛利率</span><strong className="text-right tabular-nums">{commercial.gross_margin_percent == null ? '待核价' : `${commercial.gross_margin_percent}%`}</strong><span className="text-muted-foreground">最长交期</span><strong className="text-right tabular-nums">{commercial.lead_time_days == null ? '待确认' : `${commercial.lead_time_days} 天`}</strong></div>
          {!!commercial.validation_errors?.length && <p className="mt-3 flex gap-1 text-destructive"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{commercial.validation_errors.join('；')}</p>}
          {!!commercial.validation_warnings?.length && <p className="mt-2 text-amber-700">{commercial.validation_warnings.join('；')}</p>}
        </div>
      )}
    </article>
  );
}

export function ConfigurationPanel({ workspace, onChange, products = [], projectId, canManageCatalog = false }: BasePanelProps & { products?: SolutionProductOption[]; projectId: string; canManageCatalog?: boolean }) {
  return (
    <section>
      <div className="mb-4"><h2 className="font-semibold">三档配置建议</h2><p className="text-sm text-muted-foreground">同一需求给出基础、推荐、进阶三种取舍，价格与参数仍需人工核对。</p></div>
      {canManageCatalog && <ProductCatalogManager products={products} />}
      <SolutionCPQWorkbench projectId={projectId} workspace={workspace} onChange={onChange} />
      {workspace.packages.length ? <div className="grid border-y py-4 lg:grid-cols-3">{workspace.packages.slice(0, 3).map((item, index) => <PackageColumn key={item.id} item={item} onChange={(next) => onChange({ ...workspace, packages: workspace.packages.map((current, itemIndex) => itemIndex === index ? next : current) })} />)}</div> : <div className="border-y py-16 text-center text-sm text-muted-foreground"><Sparkles className="mx-auto mb-3 h-6 w-6" />生成方案后，这里会出现基础、推荐和进阶三档配置。</div>}
    </section>
  );
}

export function DraftPanel({ workspace, onChange, projectId }: BasePanelProps & { projectId: string }) {
  if (!workspace.sections.length) return <div className="border-y py-16 text-center text-sm text-muted-foreground">当前没有章节草稿。</div>;
  return <SolutionSectionWorkbench projectId={projectId} workspace={workspace} onChange={onChange} />;
}

export function ReviewPanel({ workspace, onChange, projectId }: BasePanelProps & { projectId: string }) {
  const readiness = solutionReadiness(workspace);
  return (
    <><SolutionQualityPanel projectId={projectId} /><div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
      <section><h2 className="font-semibold">外发前人工门禁</h2><div className="mt-4 divide-y border-y">{workspace.review_gates.map((gate, index) => <label key={gate.id} className="flex cursor-pointer items-center gap-3 py-4"><input type="checkbox" checked={gate.passed} onChange={(event) => onChange({ ...workspace, review_gates: workspace.review_gates.map((item, itemIndex) => itemIndex === index ? { ...item, passed: event.target.checked } : item) })} className="h-4 w-4" /><span className="text-sm font-medium">{gate.label}</span><Badge variant={gate.passed ? 'default' : 'outline'} className="ml-auto">{gate.passed ? '已确认' : '待确认'}</Badge></label>)}</div></section>
      <aside className="border-l pl-5"><h3 className="font-medium">质量摘要</h3><dl className="mt-4 space-y-3 text-sm"><div className="flex justify-between"><dt className="text-muted-foreground">方案准备度</dt><dd className="font-semibold">{readiness.score}%</dd></div><div className="flex justify-between"><dt className="text-muted-foreground">待核验必选项</dt><dd>{readiness.mustOpen}</dd></div><div className="flex justify-between"><dt className="text-muted-foreground">证据引用</dt><dd>{readiness.evidenceCount}</dd></div><div className="flex justify-between"><dt className="text-muted-foreground">已批准章节</dt><dd>{readiness.approvedSections}</dd></div></dl><p className="mt-5 text-xs leading-5 text-muted-foreground">系统不会自动对外发送。只有证据、预算和承诺全部通过人工门禁后才开放导出。</p></aside>
    </div></>
  );
}

interface DeliveryPanelProps extends BasePanelProps {
  projectId: string;
  canDeliver?: boolean;
  versions?: SolutionVersionSummary[];
  onExport: (format: 'markdown' | 'docx' | 'pdf' | 'xlsx') => Promise<void>;
  onOutcome: (input: { outcome_type: 'proposal' | 'won' | 'lost' | 'revenue' | 'time_saved'; amount?: number; note?: string }) => Promise<void>;
  onPromoteTemplate: () => Promise<void>;
  onCreateTender: () => Promise<void>;
  onFeedback: (changeType: 'accepted' | 'edited' | 'rejected') => Promise<void>;
}

export function DeliveryPanel({ workspace, projectId, canDeliver = false, versions = [], onExport, onOutcome, onPromoteTemplate, onCreateTender, onFeedback }: DeliveryPanelProps) {
  const readiness = solutionReadiness(workspace);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section><h2 className="font-semibold">导出交付物</h2><p className="mt-1 text-sm text-muted-foreground">DOCX/PDF 面向客户，XLSX 用于需求与配置内审；导出不会再次调用 AI。</p><div className="mt-5 flex flex-wrap gap-2">{(['docx', 'pdf', 'xlsx', 'markdown'] as const).map((format) => <Button key={format} variant={format === 'docx' ? 'default' : 'outline'} disabled={!projectId || !readiness.canExport} onClick={() => onExport(format)}><FileDown className="mr-2 h-4 w-4" />{format.toUpperCase()}</Button>)}</div><Button className="mt-3" variant="outline" disabled={!projectId} onClick={onCreateTender}><Gavel className="mr-2 h-4 w-4" />转为投标项目</Button>{!readiness.canExport && <p className="mt-3 text-xs text-amber-700">请先核验必选需求、补齐证据、批准全部章节并完成人工门禁。</p>}</section>
      <section className="border-l pl-6"><h2 className="font-semibold">结果回流</h2><p className="mt-1 text-sm text-muted-foreground">记录采用、修改、赢单和丢单，持续校准行业模板。</p><div className="mt-5 flex flex-wrap gap-2"><Button variant="outline" onClick={() => onFeedback('accepted')}>采用本版</Button><Button variant="outline" onClick={() => onFeedback('edited')}>人工改写</Button><Button variant="outline" onClick={() => onOutcome({ outcome_type: 'won' })}>赢单</Button><Button variant="outline" onClick={() => onOutcome({ outcome_type: 'lost' })}>丢单</Button><Button variant="outline" onClick={() => onOutcome({ outcome_type: 'time_saved', amount: 8, note: '方案生成与整理预计节省工时' })}>节省 8 小时</Button></div><Button className="mt-4" variant="secondary" onClick={onPromoteTemplate}>沉淀为企业模板</Button></section>
      <div className="lg:col-span-2"><TenderReadinessPanel projectId={projectId} /></div>
      <SolutionConnectorDelivery projectId={projectId} canDeliver={canDeliver} />
      <section className="border-t pt-5 lg:col-span-2"><h2 className="font-semibold">版本记录</h2><p className="mt-1 text-sm text-muted-foreground">每次 AI 生成都会保留独立版本，方便审计模型、时间与降级状态。</p><SolutionVersionCompare projectId={projectId} workspace={workspace} versions={versions} /><div className="mt-4 divide-y border-y">{versions.map((version) => <div key={version.id} className="flex flex-wrap items-center gap-3 py-3 text-sm"><span className="font-medium">v{version.version_number}</span><span className="min-w-0 flex-1 truncate">{version.title}</span><Badge variant="outline">{version.generation_metadata?.degraded ? '兜底草稿' : version.generation_metadata?.model || '模型未记录'}</Badge>{version.created_at && <time className="text-xs text-muted-foreground">{new Date(version.created_at).toLocaleString('zh-CN')}</time>}</div>)}{!versions.length && <div className="py-8 text-center text-sm text-muted-foreground">生成第一版方案后，版本记录会出现在这里。</div>}</div></section>
    </div>
  );
}
