import { describe, expect, it } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';

function source(path: string) {
  return readFileSync(resolve(process.cwd(), path), 'utf8');
}

describe('frontend density guard', () => {
  it('keeps inbox evidence and low-priority work behind progressive disclosure', () => {
    const inbox = source('src/pages/InboxPage.tsx');

    expect(inbox).toContain('expanded &&');
    expect(inbox).toContain('showLaterItems');
    expect(inbox).toContain('查看稍后');
  });

  it('keeps core business AI surfaces as compact next-action strips', () => {
    const crm = source('src/pages/crm/CRMPage.tsx');
    const customerDetail = source('src/pages/crm/CustomerDetailSheet.tsx');
    const approval = source('src/components/approval/ApprovalCenter.tsx');
    const contracts = source('src/pages/ContractManagement.tsx');
    const tender = source('src/pages/TenderAnalysisPage.tsx');

    expect(crm).not.toContain('<AIInsightPanel');
    expect(customerDetail).toContain('customer-detail-next-action');
    expect(approval).not.toContain('<AIInsightPanel');
    expect(contracts).not.toContain('<AIInsightPanel');
    expect(contracts).toContain('contract-detail-next-action');
    expect(tender).toContain('data-testid="ai-insight-panel"');
    expect(tender).toContain('TenderReportSections');
    expect(tender).toContain('useState(false)');
  });

  it('keeps hidden modules reachable through action-oriented command entries', () => {
    const commandBar = source('src/components/layout/GlobalCommandBar.tsx');
    const workspace = source('src/pages/ProductSpaceHubPage.tsx');

    expect(commandBar).toContain('AI 作战室');
    expect(commandBar).toContain('发起投标分析');
    expect(commandBar).toContain('创建合同');
    expect(commandBar).toContain('生成今日计划');
    expect(workspace).toContain('data-testid="space-next-action"');
  });

  it('keeps long AI answers summarized before full evidence is shown', () => {
    const messageBubble = source('src/components/ai/MessageBubble.tsx');

    expect(messageBubble).toContain('assistant-compact-result');
    expect(messageBubble).toContain('展开完整依据');
    expect(messageBubble).toContain('收起依据');
  });
});
