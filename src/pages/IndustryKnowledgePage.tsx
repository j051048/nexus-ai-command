import { useMemo, useState } from 'react';
import { ArrowRight, BookOpenCheck, Search, Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  SCIENTIFIC_INSTRUMENT_PROMPTS,
  SCIENTIFIC_INSTRUMENT_TYPE_LABELS,
  type ScientificInstrumentAssetType,
} from '@/config/scientificInstrumentKnowledge';
import { useIndustryKnowledgeAssets } from '@/hooks/useIndustryKnowledgeAssets';
import { cn } from '@/lib/utils';
import { KnowledgeSubnav } from '@/components/knowledge/KnowledgeSubnav';

const TYPE_FILTERS: Array<ScientificInstrumentAssetType | 'all'> = [
  'all',
  'competitor',
  'tender',
  'customer_chain',
  'sales_play',
];

const TYPE_FILTER_LABELS: Record<ScientificInstrumentAssetType | 'all', string> = {
  all: '全部资产',
  competitor: '竞品战卡',
  tender: '招投标',
  customer_chain: '决策链',
  sales_play: '销售打法',
};

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

export default function IndustryKnowledgePage() {
  const [query, setQuery] = useState('');
  const [type, setType] = useState<ScientificInstrumentAssetType | 'all'>('all');
  const { data, isLoading } = useIndustryKnowledgeAssets();
  const assets = useMemo(() => data?.items ?? [], [data?.items]);

  const filteredAssets = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return assets.filter((asset) => {
      const matchesType = type === 'all' || asset.type === type;
      const haystack = [
        asset.title,
        asset.scenario,
        asset.description,
        ...asset.tags,
        ...asset.framework,
      ]
        .join(' ')
        .toLowerCase();
      return matchesType && (!normalized || haystack.includes(normalized));
    });
  }, [assets, query, type]);

  return (
    <main className="min-h-full bg-background">
      <KnowledgeSubnav />
      <div className="mx-auto max-w-7xl space-y-5 p-6">
      <header className="grid gap-4 border-b pb-5 lg:grid-cols-[1fr_360px] lg:items-end">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary">
            <BookOpenCheck className="h-4 w-4" />
            科学仪器行业知识资产
          </div>
          <h1 className="text-2xl font-bold tracking-tight">
            把行业经验沉淀成可复用的知识资产
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            资产库覆盖竞品战卡、招投标评分、科研客户决策链和技术拜访复盘。销售、售前和管理层可以直接调用模板，让 AI 进入科学仪器行业语境。
          </p>
        </div>
        <div className="rounded-lg border bg-card p-3 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs font-medium text-muted-foreground">资产库状态</div>
            <Badge variant="outline">
              {data?.source === 'database' ? '后台资产' : data?.source === 'builtin' ? '内置资产' : '前端兜底'}
            </Badge>
          </div>
          <div className="mt-2 text-sm font-semibold">
            {data?.summary.total ?? 0} 个资产 · {data?.summary.evidence_count ?? 0} 条证据线索
          </div>
          <Button
            className="mt-3 w-full"
            size="sm"
            onClick={() =>
              triggerAI('请基于当前科学仪器行业知识资产，生成本周最值得补齐的知识库条目和负责人建议。')
            }
          >
            <Sparkles className="mr-2 h-4 w-4" />
            生成补齐计划
          </Button>
        </div>
      </header>

      <section className="flex flex-col gap-3 rounded-lg border bg-card p-4 shadow-sm lg:flex-row lg:items-center lg:justify-between">
        <div className="relative w-full lg:max-w-md">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索竞品、招标、客户类型或销售场景"
            className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none ring-offset-background focus:ring-2 focus:ring-ring"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {TYPE_FILTERS.map((filter) => (
            <Button
              key={filter}
              size="sm"
              variant={type === filter ? 'default' : 'outline'}
              onClick={() => setType(filter)}
            >
              {TYPE_FILTER_LABELS[filter]}
            </Button>
          ))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid gap-3 md:grid-cols-2">
          {isLoading && (
            <div className="rounded-lg border bg-card p-4 text-sm text-muted-foreground shadow-sm md:col-span-2">
              正在加载行业知识资产...
            </div>
          )}
          {filteredAssets.map((asset) => {
            const Icon = asset.icon;
            return (
              <article key={asset.id} className="rounded-lg border bg-card p-4 shadow-sm">
                <div className="flex gap-3">
                  <div
                    className={cn(
                      'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
                      asset.type === 'competitor' && 'bg-cyan-500/10 text-cyan-600',
                      asset.type === 'tender' && 'bg-amber-500/10 text-amber-600',
                      asset.type === 'customer_chain' && 'bg-emerald-500/10 text-emerald-600',
                      asset.type === 'sales_play' && 'bg-rose-500/10 text-rose-600',
                    )}
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{SCIENTIFIC_INSTRUMENT_TYPE_LABELS[asset.type]}</Badge>
                      <span className="text-xs text-muted-foreground">{asset.scenario}</span>
                    </div>
                    <h2 className="mt-2 text-base font-semibold leading-6">{asset.title}</h2>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">{asset.description}</p>
                  </div>
                </div>

                <div className="mt-4 space-y-2">
                  {asset.framework.map((item) => (
                    <div key={item} className="flex gap-2 text-sm leading-6">
                      <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-primary" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  {asset.owner && <Badge variant="outline">Owner: {asset.owner}</Badge>}
                  {asset.version && <Badge variant="outline">v{asset.version}</Badge>}
                  {typeof asset.evidenceCount === 'number' && (
                    <Badge variant="outline">{asset.evidenceCount} 条证据</Badge>
                  )}
                  {asset.tags.map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>

                <Button className="mt-4 w-full" variant="outline" onClick={() => triggerAI(asset.aiPrompt)}>
                  <Sparkles className="mr-2 h-4 w-4" />
                  用 AI 套用此资产
                </Button>
              </article>
            );
          })}
        </div>

        <aside className="space-y-3">
          <section className="rounded-lg border bg-card p-4 shadow-sm">
            <h2 className="font-semibold">常用行业 Prompt</h2>
            <div className="mt-3 space-y-2">
              {SCIENTIFIC_INSTRUMENT_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => triggerAI(prompt)}
                  className="w-full rounded-lg border bg-background/70 p-3 text-left text-sm leading-6 transition-colors hover:bg-accent"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </section>

          <section className="rounded-lg border bg-card p-4 shadow-sm">
            <h2 className="font-semibold">资产化规则</h2>
            <div className="mt-3 space-y-3 text-sm leading-6 text-muted-foreground">
              <p>每个资产必须能回答三个问题：适用什么场景、需要什么证据、下一步动作是什么。</p>
              <p>竞品、招标和客户决策链优先沉淀为模板，再由 AI 根据客户和项目上下文生成具体材料。</p>
            </div>
          </section>
        </aside>
      </section>
      </div>
    </main>
  );
}
