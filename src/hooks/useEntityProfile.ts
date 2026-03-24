import { useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';

export interface KGTriple {
  id: string;
  source_entity: string;
  source_type: string;
  relationship: string;
  destination_entity: string;
  destination_type: string;
  strength: number;
  occurrences: number;
  updated_at: string;
}

export interface EntityAlias {
  alias: string;
  canonical_name: string;
}

export interface EntityProfile {
  entity: string;
  triple_count: number;
  triples: KGTriple[];
  aliases: EntityAlias[];
}

/**
 * 获取实体画像 — 聚合 knowledge_graph_triples 中某实体的所有关系
 */
export function useEntityProfile(entity: string | null) {
  return useQuery({
    queryKey: ['entity-profile', entity],
    queryFn: async (): Promise<EntityProfile> => {
      const resp = await aiClient.fetch<{ data: EntityProfile }>(
        `api/memories/entity-profile?entity=${encodeURIComponent(entity!)}&limit=30`
      );
      return resp.data;
    },
    enabled: !!entity && entity.length >= 1,
    staleTime: 60_000,
    retry: false,
  });
}
