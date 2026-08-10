import type {
  RequirementCategory,
  TenderDraftSection,
  TenderRequirement,
  TenderReviewGate,
  TenderStage,
  TenderWorkspaceState,
} from './types';

export const TENDER_STAGE_DEFINITIONS: Array<{
  id: TenderStage;
  shortLabel: string;
  label: string;
  description: string;
}> = [
  { id: 'intake', shortLabel: '立项', label: '项目与文件', description: '确认项目边界并上传招标文件' },
  { id: 'review', shortLabel: '审阅', label: '风险审阅', description: '先识别否决项、扣分项与缺失材料' },
  { id: 'matrix', shortLabel: '应答', label: '应答矩阵', description: '逐条绑定响应、证据与责任人' },
  { id: 'draft', shortLabel: '草拟', label: '标书草拟', description: '按已核验矩阵生成章节初稿' },
  { id: 'quality', shortLabel: '复核', label: '质量复核', description: '校验一致性、合规性与签章材料' },
  { id: 'delivery', shortLabel: '交付', label: '定稿交付', description: '人工确认后导出与提交' },
];

export const DEFAULT_DRAFT_SECTIONS: TenderDraftSection[] = [
  { id: 'cover-letter', title: '投标函与承诺', purpose: '投标声明、有效期与法定承诺', status: 'not_started' },
  { id: 'qualification', title: '资格证明', purpose: '资质、业绩、授权与财务材料', status: 'not_started' },
  { id: 'technical', title: '技术响应方案', purpose: '逐项响应参数、应用方案与配置', status: 'not_started' },
  { id: 'implementation', title: '实施与验收', purpose: '交付、安装、培训、验收与里程碑', status: 'not_started' },
  { id: 'service', title: '售后服务', purpose: '质保、响应时效、备件与校准支持', status: 'not_started' },
  { id: 'commercial', title: '商务与报价', purpose: '报价结构、付款条件与有效期', status: 'not_started' },
];

export const DEFAULT_REVIEW_GATES: TenderReviewGate[] = [
  { id: 'mandatory', label: '否决项已逐条复核', description: '资格、签章、有效期和强制条款均有人确认', status: 'pending', required: true },
  { id: 'technical', label: '技术参数有证据', description: '每项响应均绑定产品资料或检测依据', status: 'pending', required: true },
  { id: 'commercial', label: '商务口径一致', description: '报价、交期、付款与质保口径一致', status: 'pending', required: true },
  { id: 'approval', label: '负责人批准定稿', description: '最终外发前必须由负责人确认', status: 'pending', required: true },
];

export function createTenderWorkspace(): TenderWorkspaceState {
  return {
    schema_version: 'tender-workspace.v1',
    active_stage: 'intake',
    source_document_id: null,
    source_document_name: null,
    requirements: [],
    response_matrix: [],
    draft_sections: DEFAULT_DRAFT_SECTIONS.map((section) => ({ ...section })),
    review_gates: DEFAULT_REVIEW_GATES.map((gate) => ({ ...gate })),
    artifacts: [],
    extension_data: {},
  };
}

function classifyRequirement(text: string): RequirementCategory {
  if (/否决|废标|必须|不得|资格|签章|密封|有效期/i.test(text)) return 'mandatory';
  if (/评分|分值|得分|权重|加分/i.test(text)) return 'scoring';
  if (/报价|付款|商务|税率|保证金|质保金/i.test(text)) return 'commercial';
  if (/交付|安装|验收|培训|工期|截止|开标/i.test(text)) return 'delivery';
  return 'technical';
}

function cleanLine(value: string) {
  return value
    .replace(/^#{1,6}\s*/, '')
    .replace(/^[-*+]\s*/, '')
    .replace(/^\d+[.)、]\s*/, '')
    .replace(/\*\*/g, '')
    .trim();
}

export function requirementsFromReport(report: string): TenderRequirement[] {
  const candidates = report
    .split('\n')
    .map(cleanLine)
    .filter((line) => line.length >= 10 && line.length <= 260)
    .filter((line) => /否决|废标|必须|不得|要求|参数|偏离|评分|材料|证明|交付|验收|报价|资质/i.test(line));

  const unique = [...new Set(candidates)].slice(0, 40);
  return unique.map((line, index) => ({
    id: `requirement-${index + 1}`,
    category: classifyRequirement(line),
    requirement: line,
    source_excerpt: line,
    response: '',
    evidence_ref: '',
    owner: '',
    status: /否决|废标|不得/i.test(line) ? 'blocked' : 'pending',
    ai_generated: true,
  }));
}

export function mergeReportIntoWorkspace(
  current: TenderWorkspaceState,
  report: string,
  documentId: string | null,
  documentName: string | null,
): TenderWorkspaceState {
  const extracted = requirementsFromReport(report);
  const existingByExcerpt = new Map(current.response_matrix.map((item) => [item.source_excerpt, item]));
  const matrix = extracted.map((item) => existingByExcerpt.get(item.source_excerpt) || item);
  const now = new Date().toISOString();
  return {
    ...current,
    active_stage: 'review',
    source_document_id: documentId,
    source_document_name: documentName,
    requirements: extracted,
    response_matrix: matrix,
    artifacts: [
      ...current.artifacts.filter((item) => item.document_id !== documentId || !documentId),
      {
        id: documentId ? `analysis-${documentId}` : `analysis-${now}`,
        name: documentName || '标书分析报告',
        kind: 'analysis',
        status: 'ready',
        document_id: documentId || undefined,
        created_at: now,
      },
    ],
  };
}

export function tenderReadiness(workspace: TenderWorkspaceState) {
  const matrix = workspace.response_matrix;
  const answered = matrix.filter((item) => item.status === 'ready' && item.response.trim()).length;
  const gaps = matrix.filter((item) => item.status === 'gap' || item.status === 'blocked').length;
  const evidenceGaps = matrix.filter((item) => ['mandatory', 'technical', 'scoring'].includes(item.category) && !item.evidence_ref.trim()).length;
  const ownerGaps = matrix.filter((item) => !item.owner.trim()).length;
  const blockedMandatory = matrix.filter((item) => item.category === 'mandatory' && item.status === 'blocked').length;
  const approvedSections = workspace.draft_sections.filter((item) => item.status === 'approved').length;
  const passedGates = workspace.review_gates.filter((item) => item.status === 'passed').length;
  const totalChecks = Math.max(1, matrix.length + workspace.draft_sections.length + workspace.review_gates.length);
  const completed = answered + approvedSections + passedGates;
  const reviewReasons = [
    evidenceGaps ? `${evidenceGaps} 项关键响应缺少证据` : '',
    ownerGaps ? `${ownerGaps} 项尚未指定责任人` : '',
    blockedMandatory ? `${blockedMandatory} 个否决项仍被阻塞` : '',
  ].filter(Boolean);
  return {
    score: Math.round((completed / totalChecks) * 100),
    answered,
    totalRequirements: matrix.length,
    gaps,
    evidenceGaps,
    ownerGaps,
    blockedMandatory,
    reviewReasons,
    approvedSections,
    passedGates,
    canDeliver:
      matrix.length > 0 &&
      gaps === 0 &&
      evidenceGaps === 0 &&
      ownerGaps === 0 &&
      blockedMandatory === 0 &&
      workspace.review_gates.filter((item) => item.required).every((item) => item.status === 'passed'),
  };
}

export const CATEGORY_LABELS: Record<RequirementCategory, string> = {
  mandatory: '否决项',
  technical: '技术',
  commercial: '商务',
  scoring: '评分',
  delivery: '交付',
};
