import type {
  SolutionBrief,
  SolutionProject,
  SolutionStage,
  SolutionWorkspaceState,
} from './types';

export const SOLUTION_STAGE_DEFINITIONS: Array<{
  id: SolutionStage;
  label: string;
  shortLabel: string;
  description: string;
}> = [
  { id: 'brief', label: '客户简报', shortLabel: '需求', description: '客户、场景与预算' },
  { id: 'requirements', label: '需求澄清', shortLabel: '澄清', description: '必选项与待核验' },
  { id: 'configuration', label: '配置方案', shortLabel: '配置', description: '基础、推荐、进阶' },
  { id: 'draft', label: '方案成稿', shortLabel: '成稿', description: '章节与证据引用' },
  { id: 'review', label: '人工审校', shortLabel: '审校', description: '参数、承诺与预算' },
  { id: 'delivery', label: '交付复盘', shortLabel: '交付', description: '导出与结果回流' },
];

export function createSolutionWorkspace(brief: Partial<SolutionBrief> = {}): SolutionWorkspaceState {
  return {
    schema_version: 'solution-workspace.v1',
    active_stage: 'brief',
    brief: { title: '', ...brief },
    requirements: [],
    packages: [],
    sections: [],
    review_gates: [
      { id: 'budget', label: '预算范围已核对', passed: false },
      { id: 'evidence', label: '关键参数有企业资料依据', passed: false },
      { id: 'claims', label: '外部承诺已由负责人确认', passed: false },
    ],
    artifacts: [],
    generation: {},
    quality: {},
    extension_data: { output_connectors: [], template_id: brief.template_id ?? null },
  };
}

export function solutionReadiness(workspace: SolutionWorkspaceState) {
  const verified = workspace.requirements.filter((item) => item.status === 'verified').length;
  const mustOpen = workspace.requirements.filter(
    (item) => item.priority === 'must'
      && (item.status !== 'verified' || !item.evidence_ref?.trim()),
  ).length;
  const approvedSections = workspace.sections.filter((item) => item.status === 'approved').length;
  const passedGates = workspace.review_gates.filter((gate) => gate.passed).length;
  const evidenceCount = workspace.sections.reduce(
    (total, section) => total + section.evidence_refs.length,
    0,
  );
  const scoreParts = [
    workspace.brief.customer_name ? 8 : 0,
    workspace.brief.application_scenario ? 8 : 0,
    workspace.requirements.length ? 12 : 0,
    mustOpen === 0 && workspace.requirements.length ? 16 : 0,
    workspace.packages.length >= 3 ? 14 : 0,
    workspace.sections.length ? 12 : 0,
    workspace.sections.length > 0 && approvedSections === workspace.sections.length ? 10 : 0,
    evidenceCount ? 10 : 0,
    workspace.review_gates.length > 0 && passedGates === workspace.review_gates.length ? 10 : 0,
  ];
  const score = scoreParts.reduce((sum, item) => sum + item, 0);
  return {
    score,
    verified,
    mustOpen,
    approvedSections,
    passedGates,
    evidenceCount,
    canExport: score === 100,
  };
}

export function completedSolutionStages(workspace: SolutionWorkspaceState): SolutionStage[] {
  const readiness = solutionReadiness(workspace);
  const completed: SolutionStage[] = [];
  if (workspace.brief.customer_name && workspace.brief.application_scenario) completed.push('brief');
  if (workspace.requirements.length > 0 && readiness.mustOpen === 0) completed.push('requirements');
  if (workspace.packages.length >= 3) completed.push('configuration');
  if (workspace.sections.length > 0) completed.push('draft');
  if (workspace.review_gates.length > 0 && readiness.passedGates === workspace.review_gates.length) completed.push('review');
  if (readiness.canExport || Object.keys(workspace.extension_data).includes('outcome')) completed.push('delivery');
  return completed;
}

export function projectBrief(project: SolutionProject): SolutionBrief {
  return {
    title: project.title,
    customer_id: project.customer_id,
    customer_name: project.customer_name,
    industry: project.industry,
    region: project.region,
    budget_min: project.budget_min,
    budget_max: project.budget_max,
    instrument_line_code: project.instrument_line_code,
    application_scenario: project.application_scenario,
    deadline: project.deadline,
  };
}
