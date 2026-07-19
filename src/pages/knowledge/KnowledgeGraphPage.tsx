import React, { useState, useMemo } from 'react';
import {
  Search,
  Network,
  TrendingUp,
  ArrowRight,
  Hash,
  Loader2,
  Shapes,
  Box,
  LinkIcon,
  BarChart3,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { KnowledgeSubnav } from '@/components/knowledge/KnowledgeSubnav';
import {
  useSearchEntities,
  useEntityRelations,
  usePatternInsights,
  type KnowledgeEntity,
} from '@/hooks/useKnowledgeGraph';

// ─── 实体类型颜色映射 ────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  person: 'bg-blue-100 text-blue-700 border-blue-200',
  organization: 'bg-purple-100 text-purple-700 border-purple-200',
  product: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  location: 'bg-amber-100 text-amber-700 border-amber-200',
  event: 'bg-rose-100 text-rose-700 border-rose-200',
  concept: 'bg-cyan-100 text-cyan-700 border-cyan-200',
  document: 'bg-indigo-100 text-indigo-700 border-indigo-200',
};

function getTypeColor(type: string): string {
  return TYPE_COLORS[type.toLowerCase()] ?? 'bg-secondary text-secondary-foreground border-border';
}

// ─── 主组件 ──────────────────────────────────────────────

export default function KnowledgeGraphPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);

  // Debounce search
  const debounceRef = React.useRef<ReturnType<typeof setTimeout>>();
  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedQuery(value), 400);
  };

  // Queries
  const { data: searchResults = [], isLoading: isSearching } = useSearchEntities(debouncedQuery);
  const { data: relations = [], isLoading: isLoadingRelations } = useEntityRelations(selectedEntityId);
  const { data: patterns, isLoading: isLoadingPatterns } = usePatternInsights();

  // 选中实体对象
  const selectedEntity = useMemo(
    () => searchResults.find((e) => e.id === selectedEntityId) ?? null,
    [searchResults, selectedEntityId],
  );

  return (
    <div className="h-full flex flex-col bg-background animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex items-center justify-between px-8 py-6 border-b border-border bg-white/50 backdrop-blur-md sticky top-0 z-10">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Network className="w-6 h-6 text-primary" />
            </div>
            关系洞察
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            从客户、产品、项目与资料之间发现可复用关系
          </p>
        </div>

        {/* Stats badges */}
        {patterns && (
          <div className="flex gap-3">
            <div className="flex items-center gap-2 px-4 py-2 bg-primary/5 rounded-xl border border-primary/10">
              <Box className="w-4 h-4 text-primary" />
              <span className="text-sm font-semibold">{patterns.total_entities}</span>
              <span className="text-xs text-muted-foreground">实体</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 bg-primary/5 rounded-xl border border-primary/10">
              <LinkIcon className="w-4 h-4 text-primary" />
              <span className="text-sm font-semibold">{patterns.total_relations}</span>
              <span className="text-xs text-muted-foreground">关系</span>
            </div>
          </div>
        )}
      </div>

      <KnowledgeSubnav />

      {/* Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Search + Entity List */}
        <div className="w-[420px] border-r border-border flex flex-col bg-secondary/5">
          {/* Search bar */}
          <div className="p-4 border-b border-border">
            <div className="relative group">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
              <Input
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                placeholder="搜索实体名称、类型..."
                className="pl-10 bg-white"
              />
              {isSearching && (
                <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-primary" />
              )}
            </div>
          </div>

          {/* Entity list */}
          <div className="flex-1 overflow-y-auto">
            {!debouncedQuery ? (
              <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                <Search className="w-10 h-10 opacity-10 mb-4" />
                <p className="text-sm font-medium">输入关键词搜索实体</p>
                <p className="text-xs mt-1">支持名称、类型等多维度检索</p>
              </div>
            ) : searchResults.length === 0 && !isSearching ? (
              <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                <Shapes className="w-10 h-10 opacity-10 mb-4" />
                <p className="text-sm font-medium">未找到匹配实体</p>
                <p className="text-xs mt-1">换个关键词试试</p>
              </div>
            ) : (
              <div className="p-3 space-y-2">
                {searchResults.map((entity) => (
                  <EntityCard
                    key={entity.id}
                    entity={entity}
                    isSelected={entity.id === selectedEntityId}
                    onClick={() =>
                      setSelectedEntityId(entity.id === selectedEntityId ? null : entity.id)
                    }
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Relations + Insights */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-dot-pattern">
          {/* Relations panel */}
          {selectedEntityId ? (
            <RelationsPanel
              entity={selectedEntity}
              relations={relations}
              isLoading={isLoadingRelations}
              onNavigate={(id) => setSelectedEntityId(id)}
            />
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Network className="w-12 h-12 opacity-10 mb-4" />
              <p className="text-sm font-medium">选择左侧实体查看关联关系</p>
            </div>
          )}

          {/* Pattern Insights */}
          <PatternInsightsPanel patterns={patterns} isLoading={isLoadingPatterns} />
        </div>
      </div>
    </div>
  );
}

// ─── EntityCard 子组件 ──────────────────────────────────

function EntityCard({
  entity,
  isSelected,
  onClick,
}: {
  entity: KnowledgeEntity;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left p-4 rounded-xl border transition-all group',
        isSelected
          ? 'bg-primary/5 border-primary/30 shadow-md shadow-primary/5'
          : 'bg-white border-border hover:border-primary/20 hover:shadow-sm',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm truncate">{entity.name}</h3>
          <div className="flex items-center gap-2 mt-2">
            <Badge
              variant="outline"
              className={cn('text-[10px] font-medium', getTypeColor(entity.entity_type))}
            >
              {entity.entity_type}
            </Badge>
            <span className="text-[10px] text-muted-foreground flex items-center gap-1">
              <LinkIcon className="w-3 h-3" />
              {entity.relation_count} 关联
            </span>
          </div>
        </div>
        <ArrowRight
          className={cn(
            'w-4 h-4 mt-1 transition-all',
            isSelected ? 'text-primary' : 'text-muted-foreground/30 group-hover:text-muted-foreground',
          )}
        />
      </div>
    </button>
  );
}

// ─── RelationsPanel 子组件 ──────────────────────────────

function RelationsPanel({
  entity,
  relations,
  isLoading,
  onNavigate,
}: {
  entity: KnowledgeEntity | null;
  relations: ReturnType<typeof useEntityRelations>['data'];
  isLoading: boolean;
  onNavigate: (id: string) => void;
}) {
  if (!entity) return null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <div className="p-1.5 bg-primary/10 rounded-lg">
            <LinkIcon className="w-4 h-4 text-primary" />
          </div>
          <span className="truncate">{entity.name}</span>
          <Badge
            variant="outline"
            className={cn('text-[10px] ml-auto', getTypeColor(entity.entity_type))}
          >
            {entity.entity_type}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-primary" />
            <span className="ml-2 text-sm text-muted-foreground">加载关系中...</span>
          </div>
        ) : !relations || relations.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Hash className="w-8 h-8 opacity-10 mx-auto mb-2" />
            <p className="text-sm">暂无关联关系</p>
          </div>
        ) : (
          <div className="space-y-2">
            {relations.map((rel) => {
              const isSource = rel.source_id === entity.id;
              const linkedName = isSource ? rel.target_name : rel.source_name;
              const linkedId = isSource ? rel.target_id : rel.source_id;

              return (
                <button
                  key={rel.id}
                  onClick={() => onNavigate(linkedId)}
                  className="w-full flex items-center gap-3 p-3 rounded-lg border border-border bg-secondary/20 hover:bg-secondary/50 hover:border-primary/20 transition-all text-left group"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">{entity.name}</span>
                      <ArrowRight className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                      <Badge variant="outline" className="text-[10px] flex-shrink-0">
                        {rel.relation_type}
                      </Badge>
                      <ArrowRight className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                      <span className="text-sm font-medium text-primary truncate">{linkedName}</span>
                    </div>
                  </div>
                  {rel.weight > 0 && (
                    <span className="text-[10px] text-muted-foreground font-mono flex-shrink-0">
                      w:{rel.weight.toFixed(1)}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ─── PatternInsightsPanel 子组件 ────────────────────────

function PatternInsightsPanel({
  patterns,
  isLoading,
}: {
  patterns: ReturnType<typeof usePatternInsights>['data'];
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          <span className="ml-2 text-sm text-muted-foreground">加载洞察数据...</span>
        </CardContent>
      </Card>
    );
  }

  if (!patterns || (patterns.entity_types.length === 0 && patterns.relation_types.length === 0)) {
    return null;
  }

  const maxEntityCount = Math.max(...patterns.entity_types.map((t) => t.count), 1);
  const maxRelationCount = Math.max(...patterns.relation_types.map((t) => t.count), 1);

  return (
    <div className="space-y-6">
      {/* Section title */}
      <div className="flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-primary" />
        <h2 className="text-sm font-bold text-muted-foreground uppercase tracking-widest">
          模式洞察
        </h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Entity type distribution */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-primary" />
              实体类型分布
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {patterns.entity_types.map((item) => (
              <div key={item.type} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <Badge
                    variant="outline"
                    className={cn('text-[10px]', getTypeColor(item.type))}
                  >
                    {item.type}
                  </Badge>
                  <span className="font-mono text-muted-foreground">{item.count}</span>
                </div>
                <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary/60 rounded-full transition-all duration-500"
                    style={{ width: `${(item.count / maxEntityCount) * 100}%` }}
                  />
                </div>
              </div>
            ))}
            {patterns.entity_types.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">暂无数据</p>
            )}
          </CardContent>
        </Card>

        {/* Relation type distribution */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-primary" />
              关系类型分布
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {patterns.relation_types.map((item) => (
              <div key={item.type} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium">{item.type}</span>
                  <span className="font-mono text-muted-foreground">{item.count}</span>
                </div>
                <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-400/60 rounded-full transition-all duration-500"
                    style={{ width: `${(item.count / maxRelationCount) * 100}%` }}
                  />
                </div>
              </div>
            ))}
            {patterns.relation_types.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">暂无数据</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Top entities */}
      {patterns.top_entities.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-amber-500" />
              高频关联实体 TOP {patterns.top_entities.length}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {patterns.top_entities.map((item, idx) => (
                <div
                  key={item.id}
                  className="flex items-center gap-3 p-3 rounded-lg border border-border bg-secondary/20"
                >
                  <span className="text-xs font-bold text-muted-foreground w-5 text-right">
                    #{idx + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{item.name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge
                        variant="outline"
                        className={cn('text-[10px]', getTypeColor(item.type))}
                      >
                        {item.type}
                      </Badge>
                      <span className="text-[10px] text-muted-foreground">
                        {item.relation_count} 关联
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
