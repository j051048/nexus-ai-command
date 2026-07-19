import { describe, expect, it } from 'vitest';

import {
  createTenderWorkspace,
  mergeReportIntoWorkspace,
  requirementsFromReport,
  tenderReadiness,
} from '@/features/tender/workspaceModel';

describe('tender workspace model', () => {
  const report = `### 否决项
- 投标文件必须由法定代表人签章，否则废标

### 技术评分
- 检出限要求小于 0.1 ppb，需提供检测报告作为证明

### 商务要求
- 交付周期不得超过 90 天，付款条件需逐条响应`;

  it('extracts traceable requirements without inventing responses', () => {
    const requirements = requirementsFromReport(report);

    expect(requirements.length).toBeGreaterThanOrEqual(3);
    expect(requirements.some((item) => item.category === 'mandatory')).toBe(true);
    expect(requirements.every((item) => item.source_excerpt === item.requirement)).toBe(true);
    expect(requirements.every((item) => item.response === '')).toBe(true);
  });

  it('merges analysis into a versioned workspace and advances to review', () => {
    const workspace = mergeReportIntoWorkspace(
      createTenderWorkspace(),
      report,
      'document-1',
      '质谱仪招标文件.pdf',
    );

    expect(workspace.schema_version).toBe('tender-workspace.v1');
    expect(workspace.active_stage).toBe('review');
    expect(workspace.source_document_id).toBe('document-1');
    expect(workspace.response_matrix.length).toBeGreaterThan(0);
    expect(workspace.artifacts[0].kind).toBe('analysis');
  });

  it('blocks delivery until evidence gaps and required human gates are cleared', () => {
    const workspace = mergeReportIntoWorkspace(createTenderWorkspace(), report, 'doc-1', '招标文件.pdf');
    expect(tenderReadiness(workspace).canDeliver).toBe(false);

    workspace.response_matrix = workspace.response_matrix.map((item) => ({
      ...item,
      response: '已响应',
      evidence_ref: '产品检测报告第 3 页',
      owner: '售前负责人',
      status: 'ready',
    }));
    workspace.review_gates = workspace.review_gates.map((gate) => ({ ...gate, status: 'passed' }));

    expect(tenderReadiness(workspace).canDeliver).toBe(true);
  });
});
