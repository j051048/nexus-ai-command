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
  original_request: string;
  source_content: string;
  title?: string;
  artifact_type: ArtifactType;
  audience: 'internal' | 'customer' | 'regulator' | 'public';
  requested_formats: ArtifactOutputFormat[];
  customer_context: Record<string, string>;
  selected_document_ids?: string[];
  session_id?: string;
  review_confirmed: boolean;
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

export async function generateArtifact(input: ArtifactGenerateInput) {
  const response = await httpClient.post('/api/artifacts/generate', input, {
    timeout: 120000,
    silentError: true,
  });
  return unwrap<ArtifactResult>(response);
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
