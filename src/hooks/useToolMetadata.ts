import { useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';

interface ToolMetadata {
  name: string;
  description: string;
  domain: string | null;
  related_tools: string[];
  required_role: string;
  is_irreversible: boolean;
  examples: Array<{ input: Record<string, unknown>; output_summary: string }>;
  gotchas: string;
}

interface ToolsMetadataResponse {
  data: {
    tools: ToolMetadata[];
    count: number;
  };
}

export function useToolMetadata() {
  const query = useQuery({
    queryKey: ['tools-metadata'],
    queryFn: async () => {
      const res = await aiClient.get<ToolsMetadataResponse>('/api/tools/metadata');
      return res.data.tools;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000,
  });

  const getRelatedTools = (toolName: string): ToolMetadata[] => {
    if (!query.data) return [];
    const tool = query.data.find((t) => t.name === toolName);
    if (!tool?.related_tools?.length) return [];
    return query.data.filter((t) => tool.related_tools.includes(t.name));
  };

  return {
    tools: query.data ?? [],
    isLoading: query.isLoading,
    getRelatedTools,
  };
}
