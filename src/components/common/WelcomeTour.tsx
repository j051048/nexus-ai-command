import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowRight,
  Building2,
  Check,
  CheckCircle2,
  FileSearch,
  FileText,
  FolderUp,
  Loader2,
  Radar,
  Sparkles,
  Upload,
  X,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { useAuth } from '@/components/auth/AuthContext';
import { dispatchAIChatMessage } from '@/components/layout/GlobalCommandBar';
import { Button } from '@/components/ui/button';
import {
  ACTIVATION_OPEN_EVENT,
  activationProgress,
  type InstrumentFamily,
} from '@/features/activation/activationState';
import { useActivationState } from '@/hooks/useActivationState';
import { httpClient } from '@/lib/httpClient';
import { cn } from '@/lib/utils';

const STEPS = [
  { id: 'knowledge', label: '上传资料' },
  { id: 'organize', label: 'AI 整理' },
  { id: 'review', label: '确认事实' },
  { id: 'first_value', label: '首份成果' },
] as const;

const INSTRUMENT_FAMILIES: Array<{ id: InstrumentFamily; label: string }> = [
  { id: 'spectroscopy', label: '光谱' },
  { id: 'chromatography', label: '色谱' },
  { id: 'mass_spectrometry', label: '质谱' },
  { id: 'energy_spectroscopy', label: '能谱' },
  { id: 'electronics', label: '电子仪器' },
];

const OUTCOMES = [
  {
    id: 'solution' as const,
    title: '生成第一份客户方案',
    description: '把产品资料变成可核验的客户方案',
    icon: Sparkles,
    route: '/growth/solutions',
  },
  {
    id: 'tender' as const,
    title: '审阅一份招标文件',
    description: '先找否决项、缺口和应答证据',
    icon: FileSearch,
    route: '/growth/tenders',
  },
  {
    id: 'opportunity' as const,
    title: '梳理目标客户机会',
    description: '建立行业、区域和产品线索画像',
    icon: Radar,
    route: '/growth/radar',
  },
];

function inferFileGroup(filename: string) {
  const normalized = filename.toLowerCase();
  if (/说明书|手册|manual|guide|spec/.test(normalized)) return '仪器手册';
  if (/竞品|竞争|competitor|compare/.test(normalized)) return '竞品资料';
  if (/案例|case|应用/.test(normalized)) return '应用案例';
  if (/投标|招标|tender|bid/.test(normalized)) return '招投标';
  if (/公司|企业|介绍|company|profile/.test(normalized)) return '企业介绍';
  return '产品资料';
}

function formatFamilies(families: InstrumentFamily[]) {
  return INSTRUMENT_FAMILIES
    .filter((item) => families.includes(item.id))
    .map((item) => item.label)
    .join('、');
}

export function WelcomeTour() {
  const navigate = useNavigate();
  const { profile } = useAuth();
  const { state, update, isComplete } = useActivationState();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedOutcome, setSelectedOutcome] = useState<(typeof OUTCOMES)[number]['id']>('solution');

  const stepIndex = Math.min(activationProgress(state.step), STEPS.length - 1);
  const selectedFamilyLabels = formatFamilies(state.instrumentFamilies);
  const availableKnowledgeCount = state.uploadedDocumentCount + selectedFiles.length;
  const isDismissed = Boolean(
    state.dismissedUntil && new Date(state.dismissedUntil).getTime() > Date.now(),
  );

  useEffect(() => {
    if (isComplete || isDismissed) return;
    const timer = window.setTimeout(() => setIsVisible(true), 450);
    return () => window.clearTimeout(timer);
  }, [isComplete, isDismissed]);

  useEffect(() => {
    const open = () => setIsVisible(true);
    window.addEventListener(ACTIVATION_OPEN_EVENT, open);
    return () => window.removeEventListener(ACTIVATION_OPEN_EVENT, open);
  }, []);

  useEffect(() => {
    if (!isVisible || state.uploadedDocumentCount > 0) return;
    let active = true;
    void httpClient.get('/api/documents', { silentError: true }).then((response) => {
      if (!active) return;
      const rows = response.data?.data?.documents ?? response.data?.documents ?? [];
      if (Array.isArray(rows) && rows.length > 0) update({ uploadedDocumentCount: rows.length });
    }).catch(() => undefined);
    return () => { active = false; };
  }, [isVisible, state.uploadedDocumentCount, update]);

  const groupedFiles = useMemo(() => {
    const names = [...state.uploadedFileNames, ...selectedFiles.map((file) => file.name)];
    return names.reduce<Record<string, number>>((groups, name) => {
      const group = inferFileGroup(name);
      groups[group] = (groups[group] ?? 0) + 1;
      return groups;
    }, {});
  }, [selectedFiles, state.uploadedFileNames]);

  const chooseFiles = useCallback((files: FileList | File[]) => {
    const next = Array.from(files).slice(0, 20);
    setSelectedFiles(next);
  }, []);

  const uploadAndContinue = useCallback(async () => {
    if (selectedFiles.length === 0) {
      if (state.uploadedDocumentCount > 0) update({ step: 'organize' });
      return;
    }
    setIsUploading(true);
    try {
      const body = new FormData();
      selectedFiles.forEach((file) => body.append('files', file));
      body.append('category', 'auto');
      body.append('visibility', 'organization');
      const response = await httpClient.post('/api/documents/upload', body, {
        headers: { 'Content-Type': 'multipart/form-data' },
        silentError: true,
      });
      const results = response.data?.data?.results ?? [];
      const accepted = Array.isArray(results)
        ? results.filter((item: { status?: string }) => item.status !== 'error')
        : [];
      const errors = Array.isArray(results)
        ? results.filter((item: { status?: string }) => item.status === 'error')
        : [];
      if (accepted.length === 0 && errors.length > 0) throw new Error('资料未能上传，请检查文件格式后重试');
      update({
        step: 'organize',
        uploadedDocumentCount: state.uploadedDocumentCount + accepted.length,
        uploadedFileNames: [...new Set([...state.uploadedFileNames, ...selectedFiles.map((file) => file.name)])],
      });
      setSelectedFiles([]);
      toast.success(`${accepted.length} 份资料已进入整理队列`);
      if (errors.length) toast.warning(`${errors.length} 份资料需要重新检查`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '资料上传失败，请重试');
    } finally {
      setIsUploading(false);
    }
  }, [selectedFiles, state.uploadedDocumentCount, state.uploadedFileNames, update]);

  const dismiss = useCallback(() => {
    update({ dismissedUntil: new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString() });
    setIsVisible(false);
  }, [update]);

  const startFirstOutcome = useCallback(() => {
    const outcome = OUTCOMES.find((item) => item.id === selectedOutcome) ?? OUTCOMES[0];
    const companyName = state.companyName.trim() || '本企业';
    const familyContext = selectedFamilyLabels || '科学仪器';
    const prompts = {
      solution: `为${companyName}启动第一份客户解决方案。主营产品线：${familyContext}；目标市场：${state.markets || '待确认'}。请先用简短问题收集客户行业、预算、地域、样品与检测目标，再只基于企业资料生成可核验方案。`,
      tender: `为${companyName}启动招标审阅。主营产品线：${familyContext}。请提示我上传招标文件，并按否决项、评分项、参数证据和待补材料四类输出审阅结果。`,
      opportunity: `为${companyName}建立首批目标客户画像。主营产品线：${familyContext}；目标市场：${state.markets || '待确认'}。请先确认区域和重点行业，再生成可执行的线索搜集任务。`,
    };
    update({
      step: 'complete',
      factsConfirmed: true,
      firstOutcome: selectedOutcome,
      completedAt: new Date().toISOString(),
      dismissedUntil: undefined,
    });
    setIsVisible(false);
    navigate(outcome.route);
    window.dispatchEvent(new CustomEvent('proactive-chat'));
    window.setTimeout(() => dispatchAIChatMessage(prompts[selectedOutcome]), 120);
  }, [navigate, selectedFamilyLabels, selectedOutcome, state.companyName, state.markets, update]);

  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/45 p-3 backdrop-blur-[2px]" role="presentation">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="activation-title"
        className="relative grid max-h-[94vh] min-h-[590px] w-full max-w-4xl overflow-hidden rounded-lg border bg-background shadow-2xl lg:grid-cols-[220px_minmax(0,1fr)]"
      >
        <aside className="border-b bg-muted/35 p-5 lg:border-b-0 lg:border-r">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Building2 className="h-4 w-4" />
            </span>
            开始使用 Nexus
          </div>
          <ol className="mt-8 grid grid-cols-4 gap-2 lg:grid-cols-1 lg:gap-1">
            {STEPS.map((step, index) => {
              const active = index === stepIndex;
              const completed = index < stepIndex;
              return (
                <li key={step.id} className={cn('flex min-w-0 items-center gap-3 rounded-md px-2 py-2.5 text-sm', active && 'bg-background shadow-sm')}>
                  <span className={cn('flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs', active && 'border-primary bg-primary text-primary-foreground', completed && 'border-emerald-600 bg-emerald-600 text-white')}>
                    {completed ? <Check className="h-3.5 w-3.5" /> : index + 1}
                  </span>
                  <span className={cn('hidden truncate lg:block', active ? 'font-medium text-foreground' : 'text-muted-foreground')}>{step.label}</span>
                </li>
              );
            })}
          </ol>
          <p className="mt-8 hidden text-xs leading-5 text-muted-foreground lg:block">
            资料只在当前企业内可见。AI 生成内容会保留来源，外发前仍由您确认。
          </p>
        </aside>

        <div className="relative flex min-h-0 flex-col">
          <button type="button" onClick={dismiss} className="absolute right-4 top-4 z-10 rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label="稍后配置" title="稍后配置">
            <X className="h-4 w-4" />
          </button>

          <div className="flex-1 overflow-y-auto p-6 pr-14 md:p-8 md:pr-16">
            {state.step === 'knowledge' && (
              <div>
                <p className="text-xs font-medium text-primary">约 3 分钟</p>
                <h1 id="activation-title" className="mt-2 text-2xl font-semibold">先把企业资料交给 AI</h1>
                <p className="mt-2 text-sm text-muted-foreground">公司介绍、产品彩页、说明书和案例都可以。系统会自动分类。</p>

                <button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault();
                    chooseFiles(event.dataTransfer.files);
                  }}
                  className="mt-7 flex min-h-44 w-full flex-col items-center justify-center rounded-lg border border-dashed bg-muted/20 px-5 text-center transition-colors hover:border-primary/60 hover:bg-primary/[0.025]"
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-md border bg-background"><FolderUp className="h-5 w-5 text-primary" /></span>
                  <span className="mt-3 text-sm font-medium">拖入资料，或点击选择</span>
                  <span className="mt-1 text-xs text-muted-foreground">支持 PDF、DOCX、PPTX、XLSX、TXT、MD，单次最多 20 份</span>
                </button>
                <input ref={inputRef} type="file" multiple className="hidden" accept=".pdf,.docx,.pptx,.xlsx,.txt,.md,.csv" onChange={(event) => event.target.files && chooseFiles(event.target.files)} />

                {(selectedFiles.length > 0 || state.uploadedDocumentCount > 0) && (
                  <div className="mt-4 flex items-center justify-between border-y py-3 text-sm">
                    <span className="flex items-center gap-2"><FileText className="h-4 w-4 text-muted-foreground" />{selectedFiles.length ? `已选择 ${selectedFiles.length} 份资料` : `企业已有 ${state.uploadedDocumentCount} 份资料`}</span>
                    {selectedFiles.length > 0 && <button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={() => setSelectedFiles([])}>清空</button>}
                  </div>
                )}

                <div className="mt-6 grid gap-3 sm:grid-cols-2">
                  <label className="text-xs text-muted-foreground">企业简称
                    <input value={state.companyName} onChange={(event) => update({ companyName: event.target.value })} placeholder={profile?.name ? `${profile.name}所在企业` : '例如：华谱仪器'} className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring" />
                  </label>
                  <label className="text-xs text-muted-foreground">重点市场
                    <input value={state.markets} onChange={(event) => update({ markets: event.target.value })} placeholder="例如：高校实验室、制药、环境检测" className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring" />
                  </label>
                </div>
              </div>
            )}

            {state.step === 'organize' && (
              <div>
                <p className="text-xs font-medium text-emerald-700">资料已接收</p>
                <h1 id="activation-title" className="mt-2 text-2xl font-semibold">AI 正在分类并建立索引</h1>
                <p className="mt-2 text-sm text-muted-foreground">您可以继续配置，后台会完成摘要、标签和检索索引。</p>
                <div className="mt-8 divide-y border-y">
                  {Object.entries(groupedFiles).map(([group, count]) => (
                    <div key={group} className="flex items-center justify-between py-4 text-sm">
                      <span className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-emerald-600" />{group}</span>
                      <span className="text-muted-foreground">{count} 份</span>
                    </div>
                  ))}
                  {!Object.keys(groupedFiles).length && (
                    <div className="flex items-center justify-between py-4 text-sm"><span>现有企业资料</span><span className="text-muted-foreground">{state.uploadedDocumentCount} 份</span></div>
                  )}
                </div>
                <div className="mt-7 flex items-start gap-3 rounded-md bg-muted/45 p-4 text-sm">
                  <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" />
                  <span>索引完成后，方案与投标助手会自动引用这些资料，不需要重复上传。</span>
                </div>
              </div>
            )}

            {state.step === 'review' && (
              <div>
                <p className="text-xs font-medium text-primary">只确认关键事实</p>
                <h1 id="activation-title" className="mt-2 text-2xl font-semibold">您的企业主要做什么？</h1>
                <p className="mt-2 text-sm text-muted-foreground">这会决定首页、快捷指令和 AI 检索范围。</p>
                <label className="mt-7 block text-xs text-muted-foreground">企业简称
                  <input value={state.companyName} onChange={(event) => update({ companyName: event.target.value })} placeholder="例如：华谱仪器" className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring" />
                </label>
                <fieldset className="mt-6">
                  <legend className="text-xs text-muted-foreground">主营产品线（可多选）</legend>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {INSTRUMENT_FAMILIES.map((family) => {
                      const selected = state.instrumentFamilies.includes(family.id);
                      return (
                        <button key={family.id} type="button" onClick={() => update({ instrumentFamilies: selected ? state.instrumentFamilies.filter((item) => item !== family.id) : [...state.instrumentFamilies, family.id] })} className={cn('flex h-9 items-center gap-2 rounded-md border px-3 text-sm transition-colors', selected ? 'border-primary bg-primary/5 text-primary' : 'text-muted-foreground hover:text-foreground')}>
                          <span className={cn('flex h-4 w-4 items-center justify-center rounded border', selected && 'border-primary bg-primary text-primary-foreground')}>{selected && <Check className="h-3 w-3" />}</span>
                          {family.label}
                        </button>
                      );
                    })}
                  </div>
                </fieldset>
                <label className="mt-6 block text-xs text-muted-foreground">重点市场
                  <input value={state.markets} onChange={(event) => update({ markets: event.target.value })} placeholder="例如：高校、制药、环境检测；华东与华南" className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring" />
                </label>
              </div>
            )}

            {state.step === 'first_value' && (
              <div>
                <p className="text-xs font-medium text-primary">配置完成</p>
                <h1 id="activation-title" className="mt-2 text-2xl font-semibold">现在产出第一份业务成果</h1>
                <p className="mt-2 text-sm text-muted-foreground">选一个目标，AI 会在对应工作台继续询问必要信息。</p>
                <div className="mt-7 divide-y border-y">
                  {OUTCOMES.map((outcome, index) => {
                    const Icon = outcome.icon;
                    const selected = selectedOutcome === outcome.id;
                    return (
                      <button key={outcome.id} type="button" onClick={() => setSelectedOutcome(outcome.id)} className={cn('flex w-full items-center gap-4 px-1 py-4 text-left transition-colors hover:bg-muted/35', selected && 'bg-primary/[0.035]')}>
                        <span className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-background', selected && 'border-primary text-primary')}><Icon className="h-4 w-4" /></span>
                        <span className="min-w-0 flex-1"><span className="flex items-center gap-2 text-sm font-medium">{outcome.title}{index === 0 && <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary">推荐</span>}</span><span className="mt-1 block text-xs text-muted-foreground">{outcome.description}</span></span>
                        <span className={cn('flex h-5 w-5 items-center justify-center rounded-full border', selected && 'border-primary bg-primary text-primary-foreground')}>{selected && <Check className="h-3 w-3" />}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <footer className="flex items-center justify-between border-t bg-muted/20 px-6 py-4 md:px-8">
            <button type="button" onClick={dismiss} className="text-sm text-muted-foreground hover:text-foreground">稍后配置</button>
            {state.step === 'knowledge' && <Button onClick={uploadAndContinue} disabled={availableKnowledgeCount === 0 || isUploading}>{isUploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}{selectedFiles.length ? '上传并整理' : '使用现有资料'}<ArrowRight className="ml-2 h-4 w-4" /></Button>}
            {state.step === 'organize' && <Button onClick={() => update({ step: 'review' })}>确认企业信息<ArrowRight className="ml-2 h-4 w-4" /></Button>}
            {state.step === 'review' && <Button onClick={() => update({ step: 'first_value', factsConfirmed: true })} disabled={state.instrumentFamilies.length === 0}>选择首个成果<ArrowRight className="ml-2 h-4 w-4" /></Button>}
            {state.step === 'first_value' && <Button onClick={startFirstOutcome}>开始工作<ArrowRight className="ml-2 h-4 w-4" /></Button>}
          </footer>
        </div>
      </section>
    </div>
  );
}

export default WelcomeTour;
