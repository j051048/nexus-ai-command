import { expect, test, type Page } from '@playwright/test';

import { fulfillJson, mockLoggedInState, setupBusinessMocks } from './fixtures/business-mocks';

const workspace = {
  schema_version: 'tender-workspace.v1',
  active_stage: 'intake',
  source_document_id: 'doc-tender-1',
  source_document_name: '高分辨质谱采购招标文件.pdf',
  requirements: [],
  response_matrix: [
    {
      id: 'requirement-1',
      category: 'technical',
      requirement: '质量分辨率须提供制造商技术资料作为证明',
      source_excerpt: '质量分辨率须提供制造商技术资料作为证明',
      response: '按原厂技术手册逐项响应',
      evidence_ref: '产品技术手册第 12 页',
      owner: '应用工程师',
      status: 'ready',
      ai_generated: true,
    },
  ],
  draft_sections: [
    { id: 'technical', title: '技术响应方案', purpose: '逐项响应技术参数', status: 'ready' },
  ],
  review_gates: [
    { id: 'mandatory', label: '否决项已逐条复核', description: '关键条款均有人确认', status: 'passed', required: true },
  ],
  artifacts: [],
  extension_data: {},
};

const project = {
  id: 101,
  project_code: 'BID-2026-0101',
  project_name: '高分辨质谱采购项目',
  title: '高分辨质谱采购项目',
  client_name: '华东分析测试中心',
  deadline: '2026-12-31T09:00:00Z',
  estimated_value: 3200000,
  status: 'active',
  compliance_status: 'reviewing',
  instrument_line_code: 'mass_spectrometry',
  workspace,
};

async function setupTenderMocks(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('hasSeenTour', 'true');
    window.localStorage.setItem('nexus_onboarding_completed', 'true');
  });
  await mockLoggedInState(page, 'boss');
  await setupBusinessMocks(page);
  await page.route('**/api/tender-workspace/projects**', async (route) => {
    await fulfillJson(route, { success: true, data: { projects: [project] } });
  });
  await page.route('**/api/documents**', async (route) => {
    await fulfillJson(route, { success: true, data: { documents: [] } });
  });
  await page.route('**/api/billing/subscription**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        subscription: {
          org_id: 'org-123',
          plan: 'enterprise',
          status: 'active',
          has_paid_access: true,
          notice_policy: 'silent',
        },
      },
    });
  });
}

test.describe('Tender workspace', () => {
  test('unifies project review, response, drafting, quality and delivery stages', async ({ page }) => {
    await setupTenderMocks(page);
    await page.goto('/growth/tenders');

    await expect(page.getByTestId('tender-workspace')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('heading', { name: '投标作战台' })).toBeVisible();
    await expect(page.getByLabel('选择投标项目')).toHaveValue('101');
    if (process.env.CAPTURE_TENDER_VISUALS === '1') {
      await page.screenshot({ path: 'test-results/tender-workspace-desktop.png', fullPage: true });
    }

    const stageRail = page.getByRole('navigation', { name: '投标作业阶段' });
    await expect(stageRail.getByRole('button')).toHaveCount(6);

    await stageRail.getByRole('button', { name: /应答/ }).click();
    await expect(page.getByRole('heading', { name: '招标应答矩阵' })).toBeVisible();
    await expect(
      page.getByRole('paragraph').filter({ hasText: '质量分辨率须提供制造商技术资料作为证明' }),
    ).toBeVisible();

    await stageRail.getByRole('button', { name: /复核/ }).click();
    await expect(page.getByRole('heading', { name: '定稿前质量门禁' })).toBeVisible();

    await stageRail.getByRole('button', { name: /交付/ }).click();
    await expect(page.getByRole('heading', { name: '已具备定稿条件' })).toBeVisible();
  });

  test('keeps legacy entry compatible and contains the mobile layout', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await setupTenderMocks(page);
    await page.goto('/tender-analysis');

    await expect(page.getByTestId('tender-workspace')).toBeVisible({ timeout: 15000 });
    const layout = await page.evaluate(() => ({
      viewport: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
    }));
    expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewport + 1);
    await expect(page.getByRole('navigation', { name: '投标作业阶段' })).toBeVisible();
    if (process.env.CAPTURE_TENDER_VISUALS === '1') {
      await page.screenshot({ path: 'test-results/tender-workspace-mobile.png', fullPage: true });
    }
  });
});
