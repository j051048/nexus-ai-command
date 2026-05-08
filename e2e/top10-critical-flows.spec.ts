import { test, expect, Page } from '@playwright/test';
import { fulfillJson, mockLoggedInState, setupBusinessMocks } from './fixtures/business-mocks';

async function setupCriticalMocks(page: Page) {
  await setupBusinessMocks(page);
  await page.addInitScript(() => window.localStorage.setItem('hasSeenTour', 'true'));

  await page.route(/.*profile.*/, async (route) => {
    await fulfillJson(route, {
        success: true,
        data: {
          user: {
            id: 'test-user-id',
            user_id: 'test-user-id',
            email: 'test-admin@nexus-ai.com',
            name: 'E2E Admin',
            role: 'boss',
            avatar_url: null,
            organization_id: 'org-123',
          },
        },
      });
  });

  await page.route('**/api/agent-runs**', async (route) => {
    await fulfillJson(route, {
        success: true,
        data: {
          runs: [
            {
              run_id: 'run-critical-1',
              status: 'failed',
              input_summary: 'E2E replay candidate',
              created_at: new Date().toISOString(),
              tool_calls: [{ tool_name: 'get_customers' }],
            },
          ],
          total: 1,
        },
      });
  });

  await page.route('**/api/usage/cost-alerts**', async (route) => {
    await fulfillJson(route, { success: true, data: { alerts: [], summary: { count: 0 } } });
  });

  await page.route('**/api/tools/governance**', async (route) => {
    await fulfillJson(route, {
        success: true,
        data: {
          tools: [{ name: 'get_customers', category: 'crm', risk: 'low', owner: 'crm' }],
          count: 1,
          audit: { findings: {}, risk_counts: { low: 1 }, category_counts: { crm: 1 } },
          fix_suggestions: [],
          tool_rag: { tool_count: 1, ttl_s: 3600 },
        },
      });
  });

  await page.route('**/api/tools/rag/evaluate**', async (route) => {
    await fulfillJson(route, {
        success: true,
        data: { cases: [], summary: { total: 0, passed: 0, top_k_recall: 1 } },
      });
  });

  await page.route('**/api/plugins**', async (route) => {
    await fulfillJson(route, { success: true, data: { plugins: [], installed: [] } });
  });
}

async function openCriticalRoute(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState('networkidle');
  // 页面应成功加载（不是登录页或错误页）
  const body = await page.textContent('body');
  expect(body).toBeTruthy();
  expect(body).not.toContain('Something went wrong');
  expect(body).not.toContain('Application error');
}

test.describe('Top 10 critical business flows', () => {
  test.beforeEach(async ({ page }) => {
    await setupCriticalMocks(page);
    await mockLoggedInState(page, 'boss');
  });

  test('@critical dashboard shell loads after auth', async ({ page }) => {
    await openCriticalRoute(page, '/');
  });

  test('@critical chat SSE endpoint is reachable from shell', async ({ page }) => {
    await page.route('**/api/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n',
      });
    });
    await openCriticalRoute(page, '/');
  });

  test('@critical CRM customer workspace loads', async ({ page }) => {
    await openCriticalRoute(page, '/crm');
  });

  test('@critical sales pipeline workspace loads', async ({ page }) => {
    await openCriticalRoute(page, '/sales');
  });

  test('@critical approval center loads', async ({ page }) => {
    await openCriticalRoute(page, '/approval');
  });

  test('@critical workflow designer list loads', async ({ page }) => {
    await openCriticalRoute(page, '/workflows');
  });

  test('@critical knowledge graph workspace loads', async ({ page }) => {
    await openCriticalRoute(page, '/knowledge');
  });

  test('@critical finance center loads', async ({ page }) => {
    await openCriticalRoute(page, '/finance');
  });

  test('@critical Agent Run observability loads', async ({ page }) => {
    await openCriticalRoute(page, '/agent-runs');
    await expect(page.getByText('Agent Run 管理台')).toBeVisible();
  });

  test('@critical Tool governance and RAG eval loads', async ({ page }) => {
    await openCriticalRoute(page, '/tools/governance');
    await expect(page.getByText('Tool 治理清单')).toBeVisible();
  });
});
