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
    expect(inbox).toContain('今日重点');
    expect(inbox).toContain('查看依据');
    expect(inbox).toContain('参考依据');
    expect(inbox).not.toContain('AI 证据链');
  });

  it('keeps core business AI surfaces as compact next-action strips', () => {
    const crm = source('src/pages/crm/CRMPage.tsx');
    const customerDetail = source('src/pages/crm/CustomerDetailSheet.tsx');
    const customerDetailAction = source('src/pages/crm/CustomerDetailActionStrip.tsx');
    const approval = source('src/components/approval/ApprovalCenter.tsx');
    const contracts = source('src/pages/ContractManagement.tsx');
    const tender = source('src/pages/TenderAnalysisPage.tsx');
    const aiPanel = source('src/components/ai/AIInsightPanel.tsx');

    expect(aiPanel).toContain('border-l-primary');
    expect(crm).toContain('<AIInsightPanel');
    expect(customerDetail).toContain('CustomerDetailActionStrip');
    expect(customerDetailAction).toContain('customer-detail-next-action');
    expect(approval).toContain('<AIInsightPanel');
    expect(contracts).toContain('<AIInsightPanel');
    expect(contracts).toContain('contract-detail-next-action');
    expect(tender).toContain('<AIInsightPanel');
    expect(tender).not.toContain('data-testid="ai-insight-panel"');
    expect(tender).toContain('TenderReportSections');
    expect(tender).toContain('useState(false)');
  });

  it('keeps hidden modules reachable through action-oriented command entries', () => {
    const commandBar = source('src/components/layout/GlobalCommandBar.tsx');
    const workspace = source('src/pages/ProductSpaceHubPage.tsx');

    expect(commandBar).toContain('助手工作台');
    expect(commandBar).not.toContain('AI 作战室');
    expect(commandBar).toContain('发起投标分析');
    expect(commandBar).toContain('创建合同');
    expect(commandBar).toContain('生成今日计划');
    expect(workspace).toContain('data-testid="space-next-action"');
  });

  it('keeps AI presence visible without turning it into a noisy hero surface', () => {
    const aiPanel = source('src/components/ai/AIInsightPanel.tsx');
    const layout = source('src/components/layout/ChatFirstLayout.tsx');
    const trustBadge = source('src/components/ai/AITrustBadge.tsx');

    expect(aiPanel).toContain('border-l-primary');
    expect(aiPanel).toContain('建议');
    expect(layout).toContain('AssistantStatusPill');
    expect(layout).toContain('助手待命');
    expect(layout).toContain('助手正在整理请求');
    expect(trustBadge).toContain('把握较高');
    expect(trustBadge).toContain('建议复核');
    expect(trustBadge).toContain('需确认');
  });

  it('keeps long AI answers summarized before full evidence is shown', () => {
    const messageBubble = source('src/components/ai/MessageBubble.tsx');

    expect(messageBubble).toContain('assistant-compact-result');
    expect(messageBubble).toContain('展开完整依据');
    expect(messageBubble).toContain('收起依据');
  });
});
