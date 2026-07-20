import { describe, expect, it } from 'vitest';

import {
  completedSolutionStages,
  createSolutionWorkspace,
  solutionReadiness,
} from '@/features/solution/workspaceModel';

function readyWorkspace() {
  const workspace = createSolutionWorkspace({
    title: '制药客户液相色谱解决方案',
    customer_name: '华东制药实验室',
    application_scenario: '原料药杂质检测',
  });
  workspace.requirements = [{
    id: 'req-1',
    title: '检出限满足方法要求',
    priority: 'must',
    status: 'verified',
    evidence_ref: '产品手册第 12 页',
  }];
  workspace.packages = [
    { id: 'essential', name: '基础方案', positioning: '', product_models: [], components: [], rationale: '', tradeoffs: [] },
    { id: 'recommended', name: '推荐方案', positioning: '', product_models: [], components: [], rationale: '', tradeoffs: [] },
    { id: 'advanced', name: '进阶方案', positioning: '', product_models: [], components: [], rationale: '', tradeoffs: [] },
  ];
  workspace.sections = [{
    id: 'summary',
    title: '方案摘要',
    content: '采用已核验配置。',
    evidence_refs: ['产品手册第 12 页'],
    status: 'approved',
  }];
  workspace.review_gates = workspace.review_gates.map((gate) => ({ ...gate, passed: true }));
  return workspace;
}

describe('solution workspace model', () => {
  it('starts as a versioned human-reviewed workspace', () => {
    const workspace = createSolutionWorkspace();

    expect(workspace.schema_version).toBe('solution-workspace.v1');
    expect(workspace.active_stage).toBe('brief');
    expect(workspace.review_gates).toHaveLength(3);
    expect(solutionReadiness(workspace).canExport).toBe(false);
  });

  it('does not treat a verified claim without evidence as delivery ready', () => {
    const workspace = readyWorkspace();
    workspace.requirements[0].evidence_ref = null;

    expect(solutionReadiness(workspace).mustOpen).toBe(1);
    expect(solutionReadiness(workspace).canExport).toBe(false);
  });

  it('requires approved sections and all human gates before export', () => {
    const workspace = readyWorkspace();
    expect(solutionReadiness(workspace).score).toBe(100);
    expect(solutionReadiness(workspace).canExport).toBe(true);
    expect(completedSolutionStages(workspace)).toEqual([
      'brief',
      'requirements',
      'configuration',
      'draft',
      'review',
      'delivery',
    ]);

    workspace.sections[0].status = 'review';
    expect(solutionReadiness(workspace).canExport).toBe(false);
  });

  it('blocks delivery when catalog configuration has deterministic errors', () => {
    const workspace = readyWorkspace();
    workspace.extension_data.commercial_validation = {
      valid: false,
      errors: ['UNKNOWN model is not in the product catalog'],
    };

    expect(solutionReadiness(workspace).commercialValid).toBe(false);
    expect(solutionReadiness(workspace).canExport).toBe(false);
    expect(solutionReadiness(workspace).score).toBe(90);
  });
});
