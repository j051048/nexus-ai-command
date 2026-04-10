import { useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';

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
  return useQuery<KnowledgeEntity[]>({
    queryKey: ['knowledge-search', query],
    queryFn: async () => {
      const res = await aiClient.get(`/api/knowledge/search?q=${encodeURIComponent(query)}`);
      const payload = res.data;
      const list = payload?.data ?? payload;
      return Array.isArray(list) ? list : [];
    },
    enabled: query.trim().length > 0,
    staleTime: 30_000,
  });
}

/**
 * 获取实体的关联关系
 * GET /api/knowledge/entity/{id}/relations
 */
export function useEntityRelations(entityId: string | null) {
  return useQuery<EntityRelation[]>({
    queryKey: ['knowledge-relations', entityId],
    queryFn: async () => {
      const res = await aiClient.get(`/api/knowledge/entity/${entityId}/relations`);
      const payload = res.data;
      const list = payload?.data ?? payload;
      return Array.isArray(list) ? list : [];
    },
    enabled: !!entityId,
    staleTime: 30_000,
  });
}

/**
 * 获取知识图谱模式洞察
 * GET /api/knowledge/patterns
 */
export function usePatternInsights() {
  return useQuery<PatternInsight>({
    queryKey: ['knowledge-patterns'],
    queryFn: async () => {
      const res = await aiClient.get('/api/knowledge/patterns');
      const payload = res.data;
      const data = payload?.data ?? payload;
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
