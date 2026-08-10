import type { ChangeEvent } from 'react';
import {
  AlertTriangle,
  Bot,
  Check,
  CheckCircle2,
  Download,
  FileCheck2,
  FilePenLine,
  FileText,
  Loader2,
  LockKeyhole,
  ListChecks,
  PackageCheck,
  Upload,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Textarea } from '@/components/ui/textarea';
import { announceDeliverable } from '@/features/deliverables/deliverableStore';
import { cn } from '@/lib/utils';

import { TenderReportSections } from './TenderReportSections';
import type {
  ResponseStatus,
  TenderDraftSection,
  TenderRequirement,
  TenderReviewGate,
  TenderStage,
  TenderWorkspaceState,
} from './types';
import { CATEGORY_LABELS, tenderReadiness } from './workspaceModel';

interface TenderWorkspaceContentProps {
  stage: TenderStage;
  workspace: TenderWorkspaceState;
  report: string | null;
  file: File | null;
  analyzing: boolean;
  progress: number;
  currentStep: number;
  steps: string[];
  projectName: string;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onStartAnalysis: () => void;
  onExportPDF: () => void;
  onWorkspaceChange: (workspace: TenderWorkspaceState) => void;
  onAIAction: (prompt: string) => void;
}

const RESPONSE_STATUS: Array<{ value: ResponseStatus; label: string }> = [
  { value: 'pending', label: '待应答' },
  { value: 'ready', label: '已满足' },
  { value: 'gap', label: '待补证据' },
  { value: 'blocked', label: '高风险' },
];

function statusTone(status: ResponseStatus) {
  if (status === 'ready') return 'text-emerald-700 bg-emerald-50 border-emerald-200';
  if (status === 'blocked') return 'text-destructive bg-destructive/5 border-destructive/20';
  if (status === 'gap') return 'text-amber-700 bg-amber-50 border-amber-200';
  return 'text-muted-foreground bg-muted/40 border-border';
}

function exportMatrixCSV(items: TenderRequirement[], projectName: string, recordResult = true) {
  const rows = [
    ['类别', '招标要求', '我方响应', '证据引用', '负责人', '状态'],
    ...items.map((item) => [
      CATEGORY_LABELS[item.category],
      item.requirement,
      item.response,
      item.evidence_ref,
      item.owner,
      RESPONSE_STATUS.find((status) => status.value === item.status)?.label || item.status,
    ]),
  ];
  const csv = `\uFEFF${rows.map((row) => row.map((cell) => `"${String(cell || '').replace(/"/g, '""')}"`).join(',')).join('\n')}`;
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  const filename = `${projectName || '投标项目'}_应答矩阵.csv`;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
  if (recordResult) announceDeliverable({
    title: `${projectName || '投标项目'}应答矩阵`,
    filename,
    format: 'csv',
    source: 'tender',
    sourceLabel: '投标作战',
    sourcePath: `${window.location.pathname}${window.location.search}`,
    sizeBytes: blob.size,
    download: () => exportMatrixCSV(items, projectName, false),
  });
}

function IntakeStage(props: TenderWorkspaceContentProps) {
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_280px]">
      <section>
        <div className="mb-5">
          <h2 className="text-base font-semibold">上传招标文件</h2>
          <p className="mt-1 text-sm text-muted-foreground">支持 PDF、DOC、DOCX。AI 先做风险诊断，不直接生成最终外发文件。</p>
        </div>
        <label
          htmlFor="tender-input"
          className={cn(
            'flex min-h-48 cursor-pointer flex-col items-center justify-center border border-dashed px-6 text-center transition-colors hover:border-primary/60 hover:bg-primary/[0.025]',
            props.file && 'border-primary/40 bg-primary/[0.025]',
          )}
        >
          <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-full border bg-background text-primary shadow-sm">
            <Upload className="h-5 w-5" />
          </span>
          <span className="text-sm font-medium">{props.file?.name || '选择招标文件'}</span>
          <span className="mt-1 text-xs text-muted-foreground">单份文件建议小于 50 MB</span>
        </label>
        <input id="tender-input" type="file" className="hidden" accept=".pdf,.doc,.docx" onChange={props.onFileChange} />
        <div className="mt-4 flex items-center gap-2">
          <Button onClick={props.onStartAnalysis} disabled={!props.file || props.analyzing}>
            {props.analyzing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Bot className="mr-2 h-4 w-4" />}
            {props.analyzing ? '正在审阅' : '开始风险审阅'}
          </Button>
          {props.file && <Button variant="outline" onClick={() => document.getElementById('tender-input')?.click()}>重新选择</Button>}
        </div>
      </section>

      <aside className="border-l pl-6">
        <h3 className="text-sm font-medium">审阅范围</h3>
        <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
          {['否决性与资格条款', '评分标准与技术偏离', '商务、交付和验收要求', '待补材料与责任分工'].map((item) => (
            <li key={item} className="flex items-start gap-2">
              <Check className="mt-0.5 h-4 w-4 text-primary" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
        <div className="mt-6 border-t pt-4 text-xs leading-5 text-muted-foreground">
          重要判断保留原文证据；没有依据的内容会标记为待补充。
        </div>
      </aside>
    </div>
  );
}

function ReviewStage(props: TenderWorkspaceContentProps) {
  if (props.analyzing) {
    return (
      <div className="mx-auto max-w-2xl py-12">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">AI 正在审阅招标文件</span>
          <span className="tabular-nums text-muted-foreground">{props.progress}%</span>
        </div>
        <Progress value={props.progress} className="mt-3 h-1.5" />
        <p className="mt-4 text-sm text-muted-foreground">{props.steps[props.currentStep] || '正在整理风险与证据'}</p>
      </div>
    );
  }

  if (!props.report) {
    return (
      <div className="flex min-h-64 flex-col items-center justify-center text-center">
        <FileText className="h-7 w-7 text-muted-foreground" />
        <h2 className="mt-4 text-sm font-semibold">尚未生成审阅结果</h2>
        <p className="mt-1 text-sm text-muted-foreground">请先在“项目与文件”上传招标文件。</p>
      </div>
    );
  }

  const readiness = tenderReadiness(props.workspace);
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_240px]">
      <section id="analysis-report-content">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">风险审阅结论</h2>
            <p className="mt-1 text-sm text-muted-foreground">AI 结果仅作为初审依据，关键条款必须人工确认。</p>
          </div>
          <Button variant="outline" size="sm" onClick={props.onExportPDF}><Download className="mr-2 h-4 w-4" />导出报告</Button>
        </div>
        <TenderReportSections report={props.report} />
      </section>
      <aside className="border-l pl-5">
        <div className="text-xs text-muted-foreground">已提取要求</div>
        <div className="mt-1 text-2xl font-semibold tabular-nums">{readiness.totalRequirements}</div>
        <div className="mt-5 text-xs text-muted-foreground">高风险或缺口</div>
        <div className="mt-1 text-2xl font-semibold tabular-nums text-amber-700">{readiness.gaps}</div>
        <Button
          className="mt-6 w-full"
          onClick={() => props.onWorkspaceChange({ ...props.workspace, active_stage: 'matrix' })}
        >
          进入应答矩阵
        </Button>
      </aside>
    </div>
  );
}

function MatrixStage(props: TenderWorkspaceContentProps) {
  const updateItem = (id: string, patch: Partial<TenderRequirement>) => {
    props.onWorkspaceChange({
      ...props.workspace,
      response_matrix: props.workspace.response_matrix.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    });
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">招标应答矩阵</h2>
          <p className="mt-1 text-sm text-muted-foreground">每一项都要有响应、证据、负责人和明确状态。</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => exportMatrixCSV(props.workspace.response_matrix, props.projectName)} disabled={!props.workspace.response_matrix.length}>
            <Download className="mr-2 h-4 w-4" />导出 CSV
          </Button>
          <Button size="sm" onClick={() => props.onAIAction(`请基于项目“${props.projectName}”的招标审阅结果，逐条生成应答矩阵草稿。每项必须包含我方响应、证据来源和待确认信息，不得编造产品参数。`)}>
            <ListChecks className="mr-2 h-4 w-4" />AI 补全建议
          </Button>
        </div>
      </div>

      {props.workspace.response_matrix.length === 0 ? (
        <div className="flex min-h-56 flex-col items-center justify-center border border-dashed text-center">
          <FileCheck2 className="h-7 w-7 text-muted-foreground" />
          <p className="mt-3 text-sm font-medium">尚无可应答条目</p>
          <p className="mt-1 text-sm text-muted-foreground">完成风险审阅后会自动提取要求。</p>
        </div>
      ) : (
        <div className="divide-y border">
          {props.workspace.response_matrix.map((item, index) => (
            <div key={item.id} className="grid gap-3 p-4 lg:grid-cols-[44px_minmax(220px,1.2fr)_minmax(240px,1fr)_150px]">
              <span className="pt-2 text-xs tabular-nums text-muted-foreground">{String(index + 1).padStart(2, '0')}</span>
              <div>
                <div className="mb-2 flex items-center gap-2">
                  <Badge variant="outline">{CATEGORY_LABELS[item.category]}</Badge>
                  {item.ai_generated && <span className="text-xs text-muted-foreground">AI 提取</span>}
                </div>
                <p className="text-sm leading-6">{item.requirement}</p>
                <details className="mt-2 text-xs text-muted-foreground">
                  <summary className="cursor-pointer">查看原文依据</summary>
                  <p className="mt-2 border-l-2 pl-3 leading-5">{item.source_excerpt}</p>
                </details>
              </div>
              <div className="space-y-2">
                <Textarea
                  value={item.response}
                  onChange={(event) => updateItem(item.id, { response: event.target.value })}
                  placeholder="填写我方响应；未知参数请写待确认"
                  className="min-h-20 resize-y"
                />
                <Input value={item.evidence_ref} onChange={(event) => updateItem(item.id, { evidence_ref: event.target.value })} placeholder="证据：产品彩页 / 检测报告 / 页码" />
              </div>
              <div className="space-y-2">
                <select value={item.status} onChange={(event) => updateItem(item.id, { status: event.target.value as ResponseStatus })} className={cn('h-9 w-full rounded-md border px-2 text-sm', statusTone(item.status))}>
                  {RESPONSE_STATUS.map((status) => <option key={status.value} value={status.value}>{status.label}</option>)}
                </select>
                <Input value={item.owner} onChange={(event) => updateItem(item.id, { owner: event.target.value })} placeholder="负责人" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DraftStage(props: TenderWorkspaceContentProps) {
  const updateSection = (id: string, patch: Partial<TenderDraftSection>) => {
    props.onWorkspaceChange({
      ...props.workspace,
      draft_sections: props.workspace.draft_sections.map((section) => (section.id === id ? { ...section, ...patch } : section)),
    });
  };
  return (
    <div>
      <div className="mb-4">
        <h2 className="text-base font-semibold">投标文件草拟</h2>
        <p className="mt-1 text-sm text-muted-foreground">AI 只基于已核验矩阵和企业知识库起草，外发前必须经过复核。</p>
      </div>
      <div className="divide-y border">
        {props.workspace.draft_sections.map((section, index) => (
          <div key={section.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
            <span className="text-xs tabular-nums text-muted-foreground">{String(index + 1).padStart(2, '0')}</span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{section.title}</div>
              <div className="mt-1 text-xs text-muted-foreground">{section.purpose}</div>
            </div>
            <select value={section.status} onChange={(event) => updateSection(section.id, { status: event.target.value as TenderDraftSection['status'] })} className="h-9 rounded-md border bg-background px-3 text-sm">
              <option value="not_started">未开始</option>
              <option value="drafting">草拟中</option>
              <option value="ready">待复核</option>
              <option value="approved">已批准</option>
            </select>
            <Button variant="outline" size="sm" onClick={() => props.onAIAction(`请为投标项目“${props.projectName}”草拟“${section.title}”章节。仅使用已经核验的应答矩阵和知识库证据，无法确认的信息标注为【待补充】，不要编造参数、资质或案例。`)}>
              <FilePenLine className="mr-2 h-4 w-4" />AI 草拟
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

function QualityStage(props: TenderWorkspaceContentProps) {
  const toggleGate = (gate: TenderReviewGate) => {
    props.onWorkspaceChange({
      ...props.workspace,
      review_gates: props.workspace.review_gates.map((item) =>
        item.id === gate.id ? { ...item, status: item.status === 'passed' ? 'pending' : 'passed' } : item,
      ),
    });
  };
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_280px]">
      <section>
        <h2 className="text-base font-semibold">定稿前质量门禁</h2>
        <p className="mt-1 text-sm text-muted-foreground">门禁是人工责任确认，不会由 AI 自动勾选。</p>
        <div className="mt-5 divide-y border">
          {props.workspace.review_gates.map((gate) => (
            <button key={gate.id} type="button" onClick={() => toggleGate(gate)} className="flex w-full items-start gap-3 p-4 text-left hover:bg-muted/40">
              <span className={cn('mt-0.5 flex h-5 w-5 items-center justify-center rounded border', gate.status === 'passed' && 'border-emerald-600 bg-emerald-600 text-white')}>
                {gate.status === 'passed' && <Check className="h-3.5 w-3.5" />}
              </span>
              <span>
                <span className="block text-sm font-medium">{gate.label}</span>
                <span className="mt-1 block text-xs text-muted-foreground">{gate.description}</span>
              </span>
              {gate.required && <Badge variant="outline" className="ml-auto">必检</Badge>}
            </button>
          ))}
        </div>
      </section>
      <aside className="border-l pl-6">
        <LockKeyhole className="h-5 w-5 text-primary" />
        <h3 className="mt-3 text-sm font-medium">合规复核原则</h3>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">技术参数、资质、报价、交期、签章与外发动作均由责任人确认。系统保留过程状态，但不替代法务与投标负责人判断。</p>
        <Button variant="outline" className="mt-5 w-full" onClick={() => props.onAIAction(`请复核投标项目“${props.projectName}”的应答一致性、参数证据、商务口径和废标风险，只输出发现的问题及修改建议。`)}>
          <ListChecks className="mr-2 h-4 w-4" />AI 辅助复核
        </Button>
      </aside>
    </div>
  );
}

function DeliveryStage(props: TenderWorkspaceContentProps) {
  const readiness = tenderReadiness(props.workspace);
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_280px]">
      <section>
        <div className="flex items-start gap-3">
          <span className={cn('flex h-10 w-10 items-center justify-center rounded-full border', readiness.canDeliver ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'bg-muted text-muted-foreground')}>
            {readiness.canDeliver ? <PackageCheck className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
          </span>
          <div>
            <h2 className="text-base font-semibold">{readiness.canDeliver ? '已具备定稿条件' : '尚未通过全部门禁'}</h2>
            <p className="mt-1 text-sm text-muted-foreground">完成度 {readiness.score}% · 应答 {readiness.answered}/{readiness.totalRequirements} · 复核 {readiness.passedGates}/{props.workspace.review_gates.length}</p>
          </div>
        </div>
        <Progress value={readiness.score} className="mt-5 h-1.5" />
        <div className="mt-8 flex flex-wrap gap-2">
          <Button onClick={() => props.onAIAction(`请基于投标项目“${props.projectName}”已核验的应答矩阵和批准章节，整理完整投标文件草稿。所有待确认信息保留【待补充】标记，禁止生成虚假资质、参数、案例或报价。`)} disabled={!props.workspace.response_matrix.length}>
            <FileText className="mr-2 h-4 w-4" />生成整本草稿
          </Button>
          <Button variant="outline" onClick={() => exportMatrixCSV(props.workspace.response_matrix, props.projectName)} disabled={!props.workspace.response_matrix.length}>导出应答矩阵</Button>
          <Button variant="outline" onClick={props.onExportPDF} disabled={!props.report}>导出审阅报告</Button>
        </div>
        {!readiness.canDeliver && (
          <div className="mt-6 border-l-2 border-amber-500 bg-amber-50/60 px-4 py-3 text-sm text-amber-900">
            <div className="font-medium">定稿前仍需处理</div>
            <div className="mt-1 text-xs leading-5">
              {readiness.reviewReasons.length
                ? readiness.reviewReasons.join('；')
                : `处理 ${readiness.gaps} 个风险缺口，并完成全部必检门禁。`}
            </div>
          </div>
        )}
      </section>
      <aside className="border-l pl-6">
        <h3 className="text-sm font-medium">交付物</h3>
        <div className="mt-4 space-y-3">
          {['投标文件草稿', '招标应答矩阵', '风险审阅报告', '证据与附件清单'].map((item) => (
            <div key={item} className="flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle2 className="h-4 w-4" />{item}
            </div>
          ))}
        </div>
        <details className="mt-6 border-t pt-4 text-xs text-muted-foreground">
          <summary className="cursor-pointer font-medium text-foreground">扩展能力</summary>
          <p className="mt-2 leading-5">已预留 DOCX/XLSX 模板渲染、电子签章、采购平台连接器和行业模板版本接口。</p>
        </details>
      </aside>
    </div>
  );
}

export function TenderWorkspaceContent(props: TenderWorkspaceContentProps) {
  if (props.stage === 'intake') return <IntakeStage {...props} />;
  if (props.stage === 'review') return <ReviewStage {...props} />;
  if (props.stage === 'matrix') return <MatrixStage {...props} />;
  if (props.stage === 'draft') return <DraftStage {...props} />;
  if (props.stage === 'quality') return <QualityStage {...props} />;
  return <DeliveryStage {...props} />;
}
