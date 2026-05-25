import { useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
import {
  SCIENTIFIC_INSTRUMENT_ICON_BY_TYPE,
  SCIENTIFIC_INSTRUMENT_KNOWLEDGE_ASSETS,
  type ScientificInstrumentAssetType,
  type ScientificInstrumentKnowledgeAsset,
} from '@/config/scientificInstrumentKnowledge';

interface IndustryKnowledgeApiAsset {
  id: string;
  title: string;
  type: ScientificInstrumentAssetType;
  scenario: string;
  description: string;
  tags: string[];
  framework: string[];
  ai_prompt: string;
  owner?: string;
  status?: 'active' | 'draft' | 'archived';
  evidence_count?: number;
  version?: number;
  updated_at?: string | null;
}

interface IndustryKnowledgeResponse {
  items: IndustryKnowledgeApiAsset[];
  summary: {
    total: number;
    by_type: Record<ScientificInstrumentAssetType, number>;
    evidence_count: number;
  };
  source: 'database' | 'builtin';
}

function fromApiAsset(asset: IndustryKnowledgeApiAsset): ScientificInstrumentKnowledgeAsset {
  return {
    id: asset.id,
    title: asset.title,
    type: asset.type,
    scenario: asset.scenario,
    description: asset.description,
    tags: asset.tags || [],
    framework: asset.framework || [],
    aiPrompt: asset.ai_prompt,
    owner: asset.owner,
    status: asset.status,
    evidenceCount: asset.evidence_count,
    version: asset.version,
    updatedAt: asset.updated_at,
    icon: SCIENTIFIC_INSTRUMENT_ICON_BY_TYPE[asset.type],
  };
}

function localSummary() {
  return {
    total: SCIENTIFIC_INSTRUMENT_KNOWLEDGE_ASSETS.length,
    by_type: {
      competitor: SCIENTIFIC_INSTRUMENT_KNOWLEDGE_ASSETS.filter((item) => item.type === 'competitor').length,
      tender: SCIENTIFIC_INSTRUMENT_KNOWLEDGE_ASSETS.filter((item) => item.type === 'tender').length,
      customer_chain: SCIENTIFIC_INSTRUMENT_KNOWLEDGE_ASSETS.filter((item) => item.type === 'customer_chain').length,
      sales_play: SCIENTIFIC_INSTRUMENT_KNOWLEDGE_ASSETS.filter((item) => item.type === 'sales_play').length,
    },
    evidence_count: SCIENTIFIC_INSTRUMENT_KNOWLEDGE_ASSETS.reduce(
      (sum, item) => sum + (item.evidenceCount ?? 0),
      0,
    ),
  };
}

export function useIndustryKnowledgeAssets() {
  return useQuery({
    queryKey: ['industry-knowledge-assets'],
    queryFn: async () => {
      try {
        const response = await aiClient.fetch<{
          success: boolean;
          data: IndustryKnowledgeResponse;
        }>('api/industry-knowledge/assets', { _silentError: true });
        return {
          items: response.data.items.map(fromApiAsset),
          summary: response.data.summary,
          source: response.data.source,
        };
      } catch {
        return {
          items: SCIENTIFIC_INSTRUMENT_KNOWLEDGE_ASSETS,
          summary: localSummary(),
          source: 'frontend-fallback' as const,
        };
      }
    },
    staleTime: 300_000,
  });
}
