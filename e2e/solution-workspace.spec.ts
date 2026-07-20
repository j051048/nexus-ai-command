import { expect, test, type Page } from '@playwright/test';

import { fulfillJson, mockLoggedInState, setupBusinessMocks } from './fixtures/business-mocks';

const workspace = {
  schema_version: 'solution-workspace.v1',
  active_stage: 'brief',
  brief: {
    title: '华东制药液相色谱升级方案',
    customer_name: '华东制药实验室',
    industry: '制药',
    instrument_line_code: 'chromatography',
    application_scenario: '原料药杂质检测',
  },
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
  extension_data: {},
};

const project = {
  id: 'solution-1',
  project_code: 'SOL-20260719-001',
  title: '华东制药液相色谱升级方案',
  customer_name: '华东制药实验室',
  status: 'discovery',
  current_version: 0,
  workspace,
};

async function setupSolutionMocks(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('hasSeenTour', 'true');
    window.localStorage.setItem('nexus_onboarding_completed', 'true');
  });
  await mockLoggedInState(page, 'boss');
  await setupBusinessMocks(page);
  await page.route('**/api/solution-workspace/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/context-options')) {
      await fulfillJson(route, {
        success: true,
        data: { customers: [], products: [], templates: [], documents: [] },
      });
      return;
    }
    if (url.pathname.endsWith('/analytics')) {
      await fulfillJson(route, {
        success: true,
        data: {
          projects: 1,
          generated_projects: 0,
          delivered_projects: 0,
          won_projects: 0,
          win_rate: 0,
          average_readiness: 0,
          feedback_events: 0,
          acceptance_rate: 0,
          delivery_events: 0,
          total_tokens: 0,
          estimated_cost_usd: 0,
        },
      });
      return;
    }
    if (url.pathname.endsWith('/versions')) {
      await fulfillJson(route, { success: true, data: { versions: [] } });
      return;
    }
    await fulfillJson(route, { success: true, data: { projects: [project] } });
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

test.describe('Solution workspace', () => {
  test('keeps customer facts, evidence review and delivery in one guided flow', async ({ page }) => {
    await setupSolutionMocks(page);
    await page.goto('/growth/solutions');

    await expect(page.getByTestId('solution-workspace')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('heading', { name: '客户解决方案工作台' })).toBeVisible();
    await expect(page.getByLabel('选择方案项目')).toHaveValue('solution-1');
    if (process.env.CAPTURE_SOLUTION_VISUALS === '1') {
      await page.screenshot({
        path: 'test-results/solution-workspace-desktop.png',
        fullPage: true,
      });
    }

    const stageRail = page.getByRole('navigation', { name: '方案作业阶段' });
    await expect(stageRail.getByRole('button')).toHaveCount(6);

    await stageRail.getByRole('button', { name: /审校/ }).click();
    await expect(page.getByRole('heading', { name: '外发前人工门禁' })).toBeVisible();

    await stageRail.getByRole('button', { name: /交付/ }).click();
    await expect(page.getByRole('heading', { name: '导出交付物' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '版本记录' })).toBeVisible();
  });

  test('contains the six-stage workspace on a mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await setupSolutionMocks(page);
    await page.goto('/growth/solutions');

    await expect(page.getByTestId('solution-workspace')).toBeVisible({ timeout: 15000 });
    const layout = await page.evaluate(() => ({
      viewport: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
    }));
    expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewport + 1);
    await expect(page.getByRole('navigation', { name: '方案作业阶段' })).toBeVisible();
    if (process.env.CAPTURE_SOLUTION_VISUALS === '1') {
      await page.screenshot({
        path: 'test-results/solution-workspace-mobile.png',
        fullPage: true,
      });
    }
  });
});
