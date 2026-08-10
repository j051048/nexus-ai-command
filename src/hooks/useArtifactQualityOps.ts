import { useQuery } from '@tanstack/react-query';

import { httpClient } from '@/lib/httpClient';

export interface ArtifactQualityMetric {
  value: number;
  target: number;
  description: string;
  ok: boolean;
}

export interface ArtifactQualityOpsSnapshot {
  slo: {
    available: boolean;
    overall: 'ok' | 'warn';
    metrics: {
      sample_size: number;
      ready_rate: number;
      avg_score: number;
      avg_evidence_coverage: number;
      avg_repair_count: number;
    };
    slo: Record<string, ArtifactQualityMetric>;
  };
  failures: {
    available: boolean;
    sample_size: number;
    failure_modes: Array<{ code: string; count: number; share: number }>;
  };
  value: {
    available: boolean;
    events: number;
    unique_artifacts: number;
    download_rate: number;
    adoption_rate: number;
    won_count: number;
    estimated_value: number;
    by_event: Record<string, number>;
  };
  jobs: {
    healthy: boolean;
    stale_running: number;
    recoveries: number;
    by_status: Record<string, number>;
  };
  ingestion: {
    healthy: boolean;
    failed: number;
    processing: number;
    stale: number;
    ready: number;
    by_status: Record<string, number>;
  };
}

function unwrap<T>(response: { data?: unknown }): T {
  const outer = response.data as { data?: T } | T | undefined;
  return (outer && typeof outer === 'object' && 'data' in outer
    ? (outer as { data: T }).data
    : outer) as T;
}

async function get<T>(path: string, days?: number): Promise<T> {
  const response = await httpClient.get(path, {
    params: days ? { days } : undefined,
    silentError: true,
  });
  return unwrap<T>(response);
}

export function useArtifactQualityOps(days: number) {
  return useQuery({
    queryKey: ['artifact-quality-ops', days],
    queryFn: async (): Promise<ArtifactQualityOpsSnapshot> => {
      const [slo, failures, value, jobs, ingestion] = await Promise.all([
        get<ArtifactQualityOpsSnapshot['slo']>('/api/artifact-quality/slo', days),
        get<ArtifactQualityOpsSnapshot['failures']>('/api/artifact-quality/failure-modes', days),
        get<ArtifactQualityOpsSnapshot['value']>('/api/artifact-quality/value-report', days),
        get<ArtifactQualityOpsSnapshot['jobs']>('/api/artifacts/jobs/health'),
        get<ArtifactQualityOpsSnapshot['ingestion']>('/api/documents/ingestion/health'),
      ]);
      return { slo, failures, value, jobs, ingestion };
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
