import { useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
import { type ApiPayload, unwrapApiData } from '@/api/response';
import { useEnterpriseQueryScope } from '@/hooks/useEnterpriseQueryScope';

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
  tools: ToolMetadata[];
  count: number;
}

export function useToolMetadata() {
  const scope = useEnterpriseQueryScope();
  const query = useQuery({
    queryKey: ['tools-metadata', ...scope.key],
    enabled: scope.enabled,
    queryFn: async ({ signal }) => {
      const res = await aiClient.get<ApiPayload<ToolsMetadataResponse>>('/api/tools/metadata', scope.options(signal));
      const data = unwrapApiData(res.data);
      if (!data || !Array.isArray(data.tools)) throw new Error('工具数据格式异常，请重试');
      return data.tools;
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
    isError: query.isError,
    getRelatedTools,
  };
}
