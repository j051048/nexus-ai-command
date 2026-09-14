import { useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
import { type ApiPayload, unwrapApiData, unwrapApiList } from '@/api/response';
import { useEnterpriseQueryScope } from '@/hooks/useEnterpriseQueryScope';

// ─── Types ──────────────────────────────────────────────

export interface KnowledgeEntity {
  id: string;
  name: string;
  entity_type: string;
  properties: Record<string, unknown>;
  relation_count: number;
  created_at: string;
}

export interface EntityRelation {
  id: string;
  source_id: string;
  source_name: string;
  target_id: string;
  target_name: string;
  relation_type: string;
  weight: number;
  properties: Record<string, unknown>;
}

export interface PatternInsight {
  entity_types: { type: string; count: number }[];
  relation_types: { type: string; count: number }[];
  top_entities: { id: string; name: string; type: string; relation_count: number }[];
  total_entities: number;
  total_relations: number;
}

// ─── Hooks ──────────────────────────────────────────────

/**
 * 搜索知识图谱实体
 * GET /api/knowledge/search?q=xxx
 */
export function useSearchEntities(query: string) {
  const scope = useEnterpriseQueryScope();
  return useQuery<KnowledgeEntity[]>({
    queryKey: ['knowledge-search', query, ...scope.key],
    queryFn: async ({ signal }) => {
      const res = await aiClient.get<ApiPayload<KnowledgeEntity[]>>(`/api/knowledge/search?q=${encodeURIComponent(query)}`, scope.options(signal));
      return unwrapApiList(res.data);
    },
    enabled: scope.enabled && query.trim().length > 0,
    staleTime: 30_000,
  });
}

/**
 * 获取实体的关联关系
 * GET /api/knowledge/entity/{id}/relations
 */
export function useEntityRelations(entityId: string | null) {
  const scope = useEnterpriseQueryScope();
  return useQuery<EntityRelation[]>({
    queryKey: ['knowledge-relations', entityId, ...scope.key],
    queryFn: async ({ signal }) => {
      const res = await aiClient.get<ApiPayload<EntityRelation[]>>(`/api/knowledge/entity/${entityId}/relations`, scope.options(signal));
      return unwrapApiList(res.data);
    },
    enabled: scope.enabled && !!entityId,
    staleTime: 30_000,
  });
}

/**
 * 获取知识图谱模式洞察
 * GET /api/knowledge/patterns
 */
export function usePatternInsights() {
  const scope = useEnterpriseQueryScope();
  return useQuery<PatternInsight>({
    queryKey: ['knowledge-patterns', ...scope.key],
    enabled: scope.enabled,
    queryFn: async ({ signal }) => {
      const res = await aiClient.get<ApiPayload<PatternInsight>>('/api/knowledge/patterns', scope.options(signal));
      const data = unwrapApiData(res.data);
      if (!data || typeof data.total_entities !== 'number' || typeof data.total_relations !== 'number') {
        throw new Error('知识关系数据格式异常，请重试');
      }
      return {
        entity_types: Array.isArray(data?.entity_types) ? data.entity_types : [],
        relation_types: Array.isArray(data?.relation_types) ? data.relation_types : [],
        top_entities: Array.isArray(data?.top_entities) ? data.top_entities : [],
        total_entities: data?.total_entities ?? 0,
        total_relations: data?.total_relations ?? 0,
      };
    },
    staleTime: 60_000,
  });
}
