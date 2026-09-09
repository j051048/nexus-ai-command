import { httpClient } from '@/lib/httpClient';

import { downloadBlob } from './exportContent';

export type ArtifactType =
  | 'customer_solution'
  | 'tender'
  | 'competitor_analysis'
  | 'policy_brief'
  | 'service_proposal'
  | 'technical_report';

export type ArtifactOutputFormat = 'docx' | 'pdf' | 'xlsx';

export interface ArtifactGenerateInput {
  delivery_requirements?: {
    required_facts: { topic: string; expected_text: string; evidence_required: boolean }[];
    forbidden_claims: string[];
    budget?: number;
    currency?: string;
    catalog_quantities?: Record<string, number>;
  };
  original_request: string;
  source_content: string;
  title?: string;
  artifact_type: ArtifactType;
  audience: 'internal' | 'customer' | 'regulator' | 'public';
  requested_formats: ArtifactOutputFormat[];
  customer_context: Record<string, string>;
  selected_document_ids?: string[];
  target_character_count?: number;
  generation_mode?: 'deep';
  session_id?: string;
  review_confirmed: boolean;
  request_key?: string;
}

export interface ArtifactGenerationJob {
  id: string;
  status: 'queued' | 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed';
  stage: string;
  progress: number;
  progress_details: Record<string, unknown>;
  artifact_id?: string;
  result?: ArtifactResult;
  error?: { code: string; message: string } | null;
  attempt: number;
  max_attempts: number;
  heartbeat_at?: string | null;
  recovery_count?: number;
}

export interface ArtifactQualityFinding {
  severity: 'low' | 'medium' | 'high';
  code: string;
  message: string;
  repairable?: boolean;
}

export interface ArtifactResult {
  id: string;
  artifact_code: string;
  title: string;
  artifact_type: ArtifactType;
  artifact_label: string;
  status: string;
  approval_status: string;
  quality: {
    score: number;
    ready: boolean;
    findings: ArtifactQualityFinding[];
    dimensions: Record<string, number>;
    metrics?: {
      character_count?: number;
      target_character_count?: number;
      minimum_character_count?: number;
      table_count?: number;
      minimum_table_count?: number;
      required_section_count?: number;
      short_section_count?: number;
      executive_summary_character_count?: number;
    };
  };
  version_number: number;
  requested_formats: ArtifactOutputFormat[];
  verification_items: string[];
  evidence: {
    count: number;
    coverage: number;
    sufficient: boolean;
    missing_topics: string[];
  };
  orchestration?: {
    mode: 'deep';
    version: string;
    stage_count: number;
    stages: string[];
    semantic_score: number;
    semantic_passed: boolean;
    repair_count: number;
  };
  download_urls: Partial<Record<ArtifactOutputFormat, string>>;
}

export interface ArtifactSummary {
  id: string;
  title: string;
  artifact_type: ArtifactType;
  status: string;
  approval_status: string;
  quality_score: number;
  version_number: number;
  requested_formats: ArtifactOutputFormat[];
  created_at: string;
  updated_at: string;
  evidence_count?: number;
  evidence_coverage?: number;
  character_count?: number;
}

export interface ArtifactSourceDocument {
  id: string;
  name: string;
  doc_type?: string;
  status?: string;
  review_status?: string;
  quality_score?: number;
}

function unwrap<T>(value: unknown): T {
  const response = value as { data?: { data?: T } | T };
  const outer = response?.data;
  if (outer && typeof outer === 'object' && 'data' in outer) {
    return (outer as { data: T }).data;
  }
  return outer as T;
}

export interface ArtifactPreview extends ArtifactResult {
  content_markdown: string;
  requirements: { target_character_count?: number; minimum_character_count?: number };
  sources: { title: string; document_id: string; source_version?: string }[];
  usage: { total_tokens?: number; call_cost?: number };
  checkpoint_hits: number;
  revision_of?: string;
}

export async function getArtifactPreview(id: string) {
  return unwrap<ArtifactPreview>(await httpClient.get(`/api/artifacts/${id}/preview`, { silentError: true }));
}

export async function reviseArtifact(id: string, instructions: string, requestKey: string) {
  return unwrap<ArtifactGenerationJob>(await httpClient.post(`/api/artifacts/${id}/revisions`, {
    instructions, request_key: requestKey,
  }, { silentError: true }));
}

const sleep = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

export async function listArtifactJobs() {
  const response = await httpClient.get('/api/artifacts/jobs', { silentError: true });
  return unwrap<{ jobs: ArtifactGenerationJob[] }>(response).jobs;
}

export async function retryArtifactJob(jobId: string) {
  const response = await httpClient.post(`/api/artifacts/jobs/${jobId}/retry`, undefined, { silentError: true });
  return unwrap<ArtifactGenerationJob>(response);
}

export async function getArtifactJob(jobId: string) {
  const response = await httpClient.get(`/api/artifacts/jobs/${jobId}`, {
    timeout: 30000,
    silentError: true,
  });
  return unwrap<ArtifactGenerationJob>(response);
}

export async function cancelArtifactJob(jobId: string) {
  const response = await httpClient.post(`/api/artifacts/jobs/${jobId}/cancel`, undefined, {
    timeout: 30000,
    silentError: true,
  });
  return unwrap<ArtifactGenerationJob>(response);
}

export async function generateArtifact(
  input: ArtifactGenerateInput,
  onProgress?: (job: ArtifactGenerationJob) => void,
) {
  const requestKey = input.request_key
    || (typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `artifact-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  const response = await httpClient.post('/api/artifacts/jobs', {
    ...input,
    request_key: requestKey,
  }, {
    timeout: 30000,
    silentError: true,
  });
  return waitForArtifactJob(unwrap<ArtifactGenerationJob>(response), onProgress);
}

export async function waitForArtifactJob(
  initialJob: ArtifactGenerationJob,
  onProgress?: (job: ArtifactGenerationJob) => void,
) {
  let job = initialJob;
  let failures = 0;
  onProgress?.(job);
  const deadline = Date.now() + 15 * 60 * 1000;
  while (!['completed', 'failed', 'cancelled'].includes(job.status)) {
    if (Date.now() >= deadline) {
      throw new Error('成果仍在后台制作，可稍后在成果中心继续查看');
    }
    await sleep(Math.min(1200 * 2 ** failures, 10000));
    try {
      job = await getArtifactJob(job.id);
      failures = 0;
    } catch (error) {
      const status = (error as { response?: { status?: number } }).response?.status;
      if (status && status < 500 && ![408, 429].includes(status)) throw error;
      failures += 1;
      if (failures >= 5) throw new Error('暂时无法连接，任务仍保留在成果中心，请勿重复提交');
      continue;
    }
    onProgress?.(job);
  }
  if (job.status === 'failed') {
    throw new Error(job.error?.message || '成果生成失败，请重试');
  }
  if (job.status === 'cancelled') {
    throw new Error('成果生成已取消');
  }
  if (!job.result?.id) {
    throw new Error('成果任务已结束，但未返回可下载文件');
  }
  return job.result;
}

export async function listArtifacts() {
  const response = await httpClient.get('/api/artifacts', {
    params: { limit: 40 },
    silentError: true,
  });
  return unwrap<{ artifacts: ArtifactSummary[] }>(response).artifacts;
}

export async function listArtifactSourceDocuments() {
  const response = await httpClient.get('/api/documents', { silentError: true });
  const body = response.data as {
    data?: { documents?: ArtifactSourceDocument[] };
    documents?: ArtifactSourceDocument[];
  };
  return body?.data?.documents ?? body?.documents ?? [];
}

export async function reviewArtifact(
  artifactId: string,
  decision: 'approved' | 'rejected',
  confirmations: Record<string, boolean>,
) {
  const response = await httpClient.post(
    `/api/artifacts/${artifactId}/review`,
    { decision, confirmations },
    { silentError: true },
  );
  return unwrap<ArtifactResult>(response);
}

export async function recordArtifactFeedback(
  artifactId: string,
  rating: number,
  outcome: 'used' | 'edited' | 'discarded' | 'won' | 'lost',
  comment?: string,
) {
  const response = await httpClient.post(
    `/api/artifacts/${artifactId}/feedback`,
    { rating, outcome, comment },
    { silentError: true },
  );
  return unwrap<{ artifact_id: string; recorded: boolean }>(response);
}

export async function downloadArtifact(
  artifactId: string,
  format: ArtifactOutputFormat,
  title: string,
) {
  const response = await httpClient.get(`/api/artifacts/${artifactId}/download`, {
    params: { format },
    responseType: 'blob',
    timeout: 120000,
    silentError: true,
  });
  const filename = `${title}.${format}`;
  downloadBlob(response.data as Blob, filename);
  return { filename, sizeBytes: (response.data as Blob).size };
}
